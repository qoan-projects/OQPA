from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import IGate, XGate, YGate, ZGate
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
