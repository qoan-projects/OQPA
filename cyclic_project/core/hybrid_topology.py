from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from itertools import product
import copy
from typing import Optional, List, Tuple
from core.noise_models import NoiseStrategy

class UnrolledHybridStrategy:
    """
    Implements the logic to unroll the probabilistic QPA decision tree into a set of static circuits.
    
    This class manages the recursive generation of all valid execution paths. For each path, 
    it constructs a circuit that assumes a specific sequence of measurement outcomes, 
    allowing for post-selection analysis.
    """
    def __init__(self, k: int, n_trials: int, n_registers: int = 5):
        """
        Args:
            k (int): Number of qubits per register.
            n_trials (int): Depth of the protocol.
            n_registers (int): Number of available registers.
        """
        self.k = k
        self.n_trials = n_trials
        self.n_registers = n_registers
        self.circuits_data = []  # Stores {'circuit': qc, 'conditions': {...}, 'path_name': str}

    def generate_all_paths(self, epsilon: float = 0.0, noise_strategy: Optional[NoiseStrategy] = None) -> List[dict]:
        """
        Generates all static circuits corresponding to valid paths in the decision tree.
        
        Args:
            epsilon (float): Noise parameter.
            noise_strategy (Optional[NoiseStrategy]): Strategy to apply noise.

        Returns:
            List[dict]: A list of circuit data dictionaries.
        """
        self.circuits_data = []
        
        # Initial Resources
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(self.n_registers)]
        
        # We need a pool of ancillas large enough for the max depth
        # For safety, allocate new ancillas for each trial to avoid reuse issues in static unrolling
        ancilla_pool = [QuantumRegister(1, f"anc_{i}") for i in range(self.n_trials * (self.n_registers//2))]
        
        cr_readout = ClassicalRegister(self.k, "readout")
        cr_ancillas = ClassicalRegister(len(ancilla_pool), "anc_meas")
        
        qc_template = QuantumCircuit(*qr_data, *ancilla_pool, cr_readout, cr_ancillas)
        
        # Apply Initial Noise if strategy is provided
        if noise_strategy and epsilon > 0:
            noise_strategy.apply_noise(qc_template, qr_data, epsilon)

        # Initial State: Pairs + Reserve
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append([i, i+1]) # Store indices
        reserve = self.n_registers - 1
        
        # Special Case: n_trials=0 (No Purification)
        # We just measure the reserve register immediately.
        # But we must match the structure of the recursive output.
        if self.n_trials == 0:
            final_qc = qc_template.copy()
            # Measure reserve register to readout
            for i in range(self.k):
                r_qubits = final_qc.qubits[reserve*self.k : (reserve+1)*self.k]
                final_qc.measure(r_qubits[i], final_qc.clbits[i]) 
            
            self.circuits_data.append({
                'circuit': final_qc,
                'conditions': {},
                'path_name': "path_0"
            })
            return self.circuits_data

        # Start Recursion
        self._recurse(qc_template, initial_pairs, reserve, trial=0, 
                      conditions={}, used_ancillas=0)
        
        return self.circuits_data

    def _recurse(self, current_qc: QuantumCircuit, current_pairs: List[List[int]], 
                 reserve_idx: int, trial: int, conditions: dict, used_ancillas: int):
        """
        Recursive helper to traverse the decision tree.

        Args:
            current_qc: The circuit state up to this point.
            current_pairs: List of active register pairs (indices).
            reserve_idx: Index of the reserve register.
            trial: Current trial depth.
            conditions: Accumulated post-selection conditions.
            used_ancillas: Count of ancillas used so far.
        """
        if trial >= self.n_trials:
            # End of path: Measure reserve and save
            self._finalize_path(current_qc, conditions, reserve_idx)
            return

        # 1. Expand Current Step: Parallel Tests
        num_pairs = len(current_pairs)
        outcomes = list(product([0, 1], repeat=num_pairs)) # 0=Pass, 1=Fail
        
        for outcome in outcomes:
            # Create a branch for this outcome
            branch_qc = current_qc.copy()
            branch_conditions = conditions.copy()
            
            # Apply Schur Tests & Measure Ancillas
            for i, pair in enumerate(current_pairs):
                anc_idx = used_ancillas + i
                # Ancillas start after data qubits (n_registers * k)
                anc_qubit = branch_qc.qubits[self.n_registers*self.k + anc_idx]
                
                # Apply Test Logic (Swap Test)
                rA_idx, rB_idx = pair
                rA = branch_qc.qubits[rA_idx*self.k : (rA_idx+1)*self.k]
                rB = branch_qc.qubits[rB_idx*self.k : (rB_idx+1)*self.k]
                
                self._apply_schur_test(branch_qc, anc_qubit, rA, rB)
                
                # Measure Ancilla
                cl_idx = self.k + anc_idx 
                branch_qc.measure(anc_qubit, branch_qc.clbits[cl_idx])
                
                # Record Condition
                branch_conditions[cl_idx] = outcome[i]

            # 2. Determine Survivors
            surviving_pairs = []
            for i, res in enumerate(outcome):
                if res == 0: surviving_pairs.append(current_pairs[i])
            
            num_survivors = len(surviving_pairs)

            # 3. Branching Logic based on Survivor Count
            if num_survivors >= 1:
                # A. Standard Recursive Case (Cyclic Rotation)
                # Flatten pairs to indices
                survivor_flat = [idx for p in surviving_pairs for idx in p]
                
                # Join with reserve
                active_indices = survivor_flat + [reserve_idx]
                
                # Cyclic Rotate
                self._cyclic_rotate_indices(branch_qc, active_indices)
                
                # Regroup for next layer
                new_active = active_indices 
                new_pairs = []
                for i in range(0, len(new_active) - 1, 2):
                    new_pairs.append([new_active[i], new_active[i+1]])
                new_reserve = new_active[-1]
                
                self._recurse(branch_qc, new_pairs, new_reserve, trial + 1, 
                              branch_conditions, used_ancillas + num_pairs)

            else:
                # C. Death Case (0 survivors)
                # Even if all tests fail, we must return a result (unitary process).
                # The only valid state remaining is the Reserve, as others are proven noisy.
                # So we finalize the path measuring the Reserve.
                self._finalize_path(branch_qc, branch_conditions, reserve_idx)

    def _finalize_path(self, qc, conditions, reserve_idx):
        """Helper to measure reserve and save circuit."""
        final_qc = qc.copy()
        for i in range(self.k):
            r_qubits = final_qc.qubits[reserve_idx*self.k : (reserve_idx+1)*self.k]
            final_qc.measure(r_qubits[i], final_qc.clbits[i]) 
        
        self.circuits_data.append({
            'circuit': final_qc,
            'conditions': conditions,
            'path_name': f"path_{len(self.circuits_data)}"
        })

    def _swap_registers(self, qc, idx_a, idx_b):
        """Swaps two full registers."""
        for b in range(self.k):
            q_a = qc.qubits[idx_a*self.k + b]
            q_b = qc.qubits[idx_b*self.k + b]
            qc.swap(q_a, q_b)

    def _apply_schur_test(self, qc, ancilla, reg_a, reg_b):
        """Helper to apply a standard swap test."""
        qc.h(ancilla)
        for i in range(self.k):
            qc.cswap(ancilla, reg_a[i], reg_b[i])
        qc.h(ancilla)

    def _cyclic_rotate_indices(self, qc, indices):
        """
        Applies physical SWAP gates to rotate data among the specified register indices.
        
        Args:
            qc: Circuit.
            indices: List of register indices involved in the rotation.
        """
        # Apply SWAP gates to physically rotate the states in the registers
        for i in range(len(indices)-1, 0, -1):
            idx_j = indices[i]
            idx_j_minus_1 = indices[i-1]
            
            # Swap full registers
            for b in range(self.k):
                q_j = qc.qubits[idx_j*self.k + b]
                q_j_1 = qc.qubits[idx_j_minus_1*self.k + b]
                qc.swap(q_j, q_j_1)
