from abc import ABC, abstractmethod
from typing import List, Tuple, Any
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import Parameter
from qiskit.circuit.library import IGate, XGate, YGate, ZGate, RXGate, RZGate
from qiskit_aer.noise import depolarizing_error

PAULIS = [IGate(), XGate(), YGate(), ZGate()]

class NoiseStrategy(ABC):
    """
    Abstract base class for noise application strategies.
    
    This class defines the interface for applying noise models to quantum circuits.
    """
    @abstractmethod
    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        """
        Applies noise to the given registers in the circuit.
        
        Args:
            qc (QuantumCircuit): The QuantumCircuit to modify.
            registers (List[QuantumRegister]): List of QuantumRegisters to apply noise to.
            epsilon (float): Noise parameter (e.g., depolarization probability).
        """
        pass

    def generate_bindings(self, circuit: QuantumCircuit, num_randomizations: int, epsilon: float) -> np.ndarray:
        """
        Generates parameter bindings for the circuit. 
        Only relevant for parameterized strategies.
        
        Args:
            circuit (QuantumCircuit): The parameterized circuit.
            num_randomizations (int): Number of random instances to generate.
            epsilon (float): Noise parameter.
            
        Returns:
            np.ndarray: Binding array of shape (num_randomizations, num_params).
        """
        return np.empty((num_randomizations, 0))

class StandardDepolarizingStrategy(NoiseStrategy):
    """
    Applies standard depolarizing error using qiskit-aer's noise module.
    Best for AER simulations.
    
    This strategy inserts a quantum channel (Kraus operators) representing 
    depolarizing noise into the circuit.
    """
    def __init__(self, k: int):
        """
        Args:
            k (int): Number of qubits per register (dimension of the noise).
        """
        self.k = k

    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        """
        Applies a k-qubit depolarizing error channel to each register.

        Args:
            qc (QuantumCircuit): The circuit.
            registers (List[QuantumRegister]): The target registers.
            epsilon (float): Depolarization probability.
        """
        if epsilon <= 0:
            return
        
        # Create a k-qubit depolarizing error
        noise = depolarizing_error(epsilon, self.k)
        
        for reg in registers:
            # Check if register size matches k
            if reg.size != self.k:
                # Fallback: apply to individual qubits or raise error?
                # For now assuming registers are size k as per QPA logic
                pass
            qc.append(noise, reg)

class PauliTwirlingStrategy(NoiseStrategy):
    """
    Applies random Pauli gates to simulate noise via ensemble averaging.
    Best for hardware or fake backend simulations where we want to 
    mimic global depolarizing noise by averaging over many circuits.
    
    This strategy stochastically inserts Pauli gates (I, X, Y, Z) based on the 
    noise parameter `epsilon`. When averaged over many instances, this converges 
    to a depolarizing channel.
    """
    def __init__(self, k: int):
        """
        Args:
            k (int): Number of qubits per register.
        """
        self.k = k
        self.rng = np.random.default_rng()

    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        """
        With probability 'epsilon', applies a random Pauli string to a register.
        Note: This effectively modifies the circuit IN-PLACE for a single instance.
        To get ensemble averaging, you must generate multiple circuits with this strategy.

        Args:
            qc (QuantumCircuit): The circuit.
            registers (List[QuantumRegister]): Target registers.
            epsilon (float): Depolarization probability.
        """
        if epsilon <= 0:
            return

        pauli_gates = [IGate(), XGate(), YGate(), ZGate()]
        
        for reg in registers:
            # Determine if error occurs for this register instance
            if self.rng.random() < epsilon:
                # Choose random Pauli string for the k qubits
                # Note: This means picking a random Pauli (I, X, Y, Z) for each qubit independently.
                # The "Identity string" case is INCLUDED in the possibilities here.
                # This matches Standard Depolarizing Channel definition:
                # (1-e)rho + e(I/2^k)  <-- I/2^k is random mixture of all Paulis
                for q in reg:
                    idx = self.rng.integers(0, 4)
                    p_gate = pauli_gates[idx]
                    qc.append(p_gate, [q])

    def generate_noise_ops(self, registers: List[QuantumRegister], epsilon: float) -> List[Tuple[Any, Any]]:
        """
        Generates a list of noise operations (gate, logical_qubit) without modifying the circuit.
        Used for fast-path reconstruction of noisy circuits.
        
        Args:
            registers: List of target registers.
            epsilon: Error probability.
            
        Returns:
            List[tuple]: List of (gate, qubit_object) tuples.
        """
        if epsilon <= 0:
            return []

        ops = []
        pauli_gates = [IGate(), XGate(), YGate(), ZGate()]
        
        for reg in registers:
            if self.rng.random() < epsilon:
                for q in reg:
                    idx = self.rng.integers(0, 4)
                    p_gate = pauli_gates[idx]
                    # Only add if not Identity (optimization)
                    if idx != 0: 
                        ops.append((p_gate, q))
        return ops

class ParameterizedPauliTwirlingStrategy(NoiseStrategy):
    """
    Applies parameterized rotations to simulate Pauli Twirling.
    Instead of inserting fixed I, X, Y, Z gates, it inserts:
    RZ(theta_z) * RX(theta_x)
    
    This allows a single circuit to represent all possible Pauli error configurations
    by changing parameter values.
    """
    def __init__(self, k: int):
        self.k = k
        # Registry to track created parameters so we can map them later if needed
        # However, relying on circuit.parameters is safer as per plan.
        
    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        """
        Applies parameterized RX and RZ gates to the registers.
        
        Args:
            qc: Quantum Circuit
            registers: List of registers to apply noise to
            epsilon: Not used for circuit construction, but needed for interface.
        """
        # We need to create unique parameters for every qubit in every register
        # Since this method might be called multiple times (multiple layers),
        # we need a way to ensure uniqueness. 
        # Qiskit Parameters must have unique names in a circuit.
        # We can use a counter based on existing parameters in the circuit?
        # Or just use uuid/random string.
        # Let's use a counter based on current circuit parameter count to ensure stability.
        
        current_param_count = len(qc.parameters)
        
        # Logic:
        # We need to simulate Global Register Noise.
        # With probability epsilon: The register is corrupted.
        # If corrupted: We pick a random Pauli string P from {I, X, Y, Z}^k \ {I^k}.
        # (Uniformly at random from 4^k - 1 possibilities).
        
        # We need to coordinate the parameters for all qubits in the register.
        # The 'uid' logic below handles independent qubits. We need to group them by register.
        # However, apply_noise is called per register. So we know which qubits belong together.
        
        # Problem: 'generate_bindings' is called later with just the circuit. It doesn't know which params belong to which register.
        # Solution: We can encode the register ID in the parameter name!
        # e.g., "twirl_reg{reg_index}_q{qubit_index}_x_{uid}"
        
        # But 'apply_noise' doesn't easily get a unique register index unless passed.
        # Alternative: We group parameters by the 'uid' block.
        # In 'apply_noise', we generate a block of parameters for the register.
        # In 'generate_bindings', we group these parameters back together and sample them jointly.
        
        # Let's use a shared UID for the whole register application.
        register_uid = current_param_count
        
        # We will increment current_param_count by 2 * k
        # But we loop over registers. We need to do this PER register.
        
        for reg in registers:
            register_uid = current_param_count
            current_param_count += 2 * len(reg)
            
            for i, q in enumerate(reg):
                # Name format: "twirl_{register_uid}_q{i}_x"
                # This allows us to group them later.
                px_name = f"twirl_{register_uid}_q{i}_x"
                pz_name = f"twirl_{register_uid}_q{i}_z"
                
                theta_x = Parameter(px_name)
                theta_z = Parameter(pz_name)
                
                qc.append(RZGate(theta_z), [q])
                qc.append(RXGate(theta_x), [q])

    def generate_bindings(self, circuit: QuantumCircuit, num_randomizations: int, epsilon: float) -> np.ndarray:
        """
        Generates the binding array for the parameters created by this strategy.
        
        Shape: (num_randomizations, num_params)
        
        CRITICAL: Qiskit maps bindings to circuit.parameters alphabetically/deterministically.
        We must iterate over circuit.parameters to ensure the column order matches.
        
        Logic (Global Register Noise):
        1. Identify groups of parameters belonging to the same register application (via register_uid).
        2. For each group (register):
           - With prob (1-epsilon): Apply Identity to ALL qubits (all params 0).
           - With prob epsilon: Apply a random Pauli string P from {I, X, Y, Z}^k \ {I^k}.
             (Uniformly sample one of the 4^k - 1 non-identity strings).
        """
        rng = np.random.default_rng()
        
        # Get parameters in the order Qiskit expects
        circuit_params = circuit.parameters
        num_params = len(circuit_params)
        
        if num_params == 0:
            return np.empty((num_randomizations, 0))
            
        bindings_matrix = np.zeros((num_randomizations, num_params))
        
        # Group params by register_uid
        # Map: register_uid -> { qubit_index -> {'x': param_idx, 'z': param_idx} }
        reg_map = {}
        
        for i, param in enumerate(circuit_params):
            name = param.name
            # Format: "twirl_{register_uid}_q{i}_[x|z]"
            if name.startswith("twirl_"):
                parts = name.split('_')
                # parts[0] = "twirl"
                # parts[1] = register_uid
                # parts[2] = q{i}
                # parts[3] = x or z
                
                if len(parts) >= 4:
                    r_uid = int(parts[1])
                    q_idx = int(parts[2][1:]) # remove 'q'
                    p_type = parts[3]
                    
                    if r_uid not in reg_map: reg_map[r_uid] = {}
                    if q_idx not in reg_map[r_uid]: reg_map[r_uid][q_idx] = {}
                    
                    reg_map[r_uid][q_idx][p_type] = i
        
        # Pre-compute choices for a single qubit: (theta_x, theta_z)
        # 0: I (0,0), 1: X (pi,0), 2: Z (0,pi), 3: Y (pi,pi)
        vals_x = [0.0, np.pi, 0.0, np.pi]
        vals_z = [0.0, 0.0, np.pi, np.pi]
        
        # Generate bindings for each register group
        for r_uid, qubits_map in reg_map.items():
            k = len(qubits_map) # Number of qubits in this register
            
            # Total Paulis = 4^k
            # Non-identity Paulis = 4^k - 1
            num_paulis = 4**k
            
            # For each randomization instance:
            # Decide if error occurs (prob epsilon)
            is_error = rng.random(size=num_randomizations) < epsilon
            
            # Generate random integer in [0, 4^k) for error cases
            # Note: We now include 0 (Identity) in the error distribution
            # This matches standard depolarizing channel: (1-e)rho + e(I/2^k)
            error_indices = rng.integers(0, num_paulis, size=num_randomizations)
            
            # If not error (from the (1-e) branch), index is 0 (Identity)
            final_indices = np.where(is_error, error_indices, 0)
            
            # Now decode the integer into k Pauli choices (0,1,2,3) for each qubit
            # Index i corresponds to qubit q_i? 
            # We need to map qubit indices 0..k-1 correctly.
            # Assuming qubits_map keys are 0..k-1
            sorted_q_indices = sorted(qubits_map.keys())
            
            # Decode base 4
            # We can vectorize this:
            # qubit 0: indices % 4
            # qubit 1: (indices // 4) % 4
            # ...
            
            current_val = final_indices
            for q_idx in sorted_q_indices:
                p_choice = current_val % 4
                current_val = current_val // 4
                
                # Get param indices for this qubit
                p_indices = qubits_map[q_idx]
                
                if 'x' in p_indices:
                    # Map 0,1,2,3 to theta_x
                    # Vectorized map
                    bx = np.array([vals_x[c] for c in p_choice])
                    bindings_matrix[:, p_indices['x']] = bx
                    
                if 'z' in p_indices:
                    # Map 0,1,2,3 to theta_z
                    bz = np.array([vals_z[c] for c in p_choice])
                    bindings_matrix[:, p_indices['z']] = bz
                    
        return bindings_matrix


class OldPauliTwirlingStrategy(NoiseStrategy):
    """
    Applies random Pauli gates to simulate noise via ensemble averaging.
    Best for hardware or fake backend simulations where we want to 
    mimic global depolarizing noise by averaging over many circuits.
    
    This strategy stochastically inserts Pauli gates (I, X, Y, Z) based on the 
    noise parameter `epsilon`. When averaged over many instances, this converges 
    to a depolarizing channel.
    """
    def __init__(self, k: int):
        """
        Args:
            k (int): Number of qubits per register.
        """
        self.k = k
        self.rng = np.random.default_rng()

    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        """
        With probability 'epsilon', applies a random Pauli string to a register.
        Note: This effectively modifies the circuit IN-PLACE for a single instance.
        To get ensemble averaging, you must generate multiple circuits with this strategy.

        Args:
            qc (QuantumCircuit): The circuit.
            registers (List[QuantumRegister]): The target registers.
            epsilon (float): Probability of applying a non-identity Pauli error.
        """
        if epsilon <= 0:
            return

        pauli_gates = [IGate(), XGate(), YGate(), ZGate()]
        
        for reg in registers:
            # Determine if error occurs for this register instance
            if self.rng.random() < epsilon:
                # Choose random Pauli string for the k qubits
                for q in reg:
                    # Use indices to avoid numpy object array issues
                    idx = self.rng.integers(0, 4)
                    p_gate = pauli_gates[idx]
                    qc.append(p_gate, [q])

    def generate_noise_ops(self, registers: List[QuantumRegister], epsilon: float) -> List[tuple]:
        """
        Generates a list of noise operations (gate, logical_qubit) without modifying the circuit.
        
        Args:
            registers: List of target registers.
            epsilon: Error probability.
            
        Returns:
            List[tuple]: List of (gate, qubit_object) tuples.
        """
        if epsilon <= 0:
            return []

        ops = []
        pauli_gates = [IGate(), XGate(), YGate(), ZGate()]
        
        for reg in registers:
            if self.rng.random() < epsilon:
                for q in reg:
                    idx = self.rng.integers(0, 4)
                    p_gate = pauli_gates[idx]
                    # Only add if not Identity (optimization)
                    if idx != 0: 
                        ops.append((p_gate, q))
        return ops