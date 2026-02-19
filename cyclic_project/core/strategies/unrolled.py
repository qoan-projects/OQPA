from typing import List, Dict, Any
from itertools import product
from qiskit import QuantumCircuit
from core.strategies.base import CircuitGenerationStrategy
from core.registers import QPARegisters
from core.ops import apply_schur_test, apply_cyclic_rotation_indices

class UnrolledStrategy(CircuitGenerationStrategy):
    """
    Builds a set of static circuits representing all execution paths.
    """
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        self.circuits_data = []
        
        regs = QPARegisters(self.n_registers, self.k, self.n_trials, use_ancilla_pool=True)
        qc_template = QuantumCircuit(*regs.get_circuit_registers())
        
        # Apply Initial Noise
        if self.noise_strategy and epsilon > 0:
            self.noise_strategy.apply_noise(qc_template, regs.qr_data, epsilon)

        # Initial State: Pairs + Reserve
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append([i, i+1]) # Store indices
        reserve = self.n_registers - 1
        
        if self.n_trials == 0:
            final_qc = qc_template.copy()
            for i in range(self.k):
                r_qubits = final_qc.qubits[reserve*self.k : (reserve+1)*self.k]
                # Map to readout
                final_qc.measure(r_qubits[i], regs.cr_readout[i])
            
            self.circuits_data.append({
                'circuit': final_qc,
                'conditions': {},
                'metadata': {'type': 'unrolled', 'path_name': "path_0"}
            })
            return self.circuits_data

        self._recurse(qc_template, initial_pairs, reserve, trial=0, 
                      conditions={}, total_meas_index=0, regs=regs)
        
        return self.circuits_data

    def _recurse(self, current_qc: QuantumCircuit, current_pairs: List[List[int]], 
                 reserve_idx: int, trial: int, conditions: dict, total_meas_index: int, regs: QPARegisters):
        
        if trial >= self.n_trials:
            self._finalize_path(current_qc, conditions, reserve_idx, regs)
            return

        num_pairs = len(current_pairs)
        outcomes = list(product([0, 1], repeat=num_pairs))
        
        for outcome in outcomes:
            branch_qc = current_qc.copy()
            branch_conditions = conditions.copy()
            
            for i, pair in enumerate(current_pairs):
                # Reuse ancilla qubits from pool


                anc_qubit = regs.qr_ancilla[i]
                
                rA_idx, rB_idx = pair
                rA = branch_qc.qubits[rA_idx*self.k : (rA_idx+1)*self.k]
                rB = branch_qc.qubits[rB_idx*self.k : (rB_idx+1)*self.k]
                
                apply_schur_test(branch_qc, anc_qubit, rA, rB, self.k)
                
                cl_idx = total_meas_index + i
                branch_qc.measure(anc_qubit, regs.cr_ancilla[cl_idx])
                branch_qc.reset(anc_qubit) # Reset is already present here!
                
                # Shift condition key by k because ResultProcessor maps 0..k-1 to readout
                branch_conditions[self.k + cl_idx] = outcome[i]

            surviving_pairs = []

            for i, res in enumerate(outcome):
                if res == 0: surviving_pairs.append(current_pairs[i])
            
            num_survivors = len(surviving_pairs)

            if num_survivors >= 1:
                # Regrouping Logic (Same as DynamicStrategy)
                # Note: active_indices are just indices here, so we don't need to rebuild pairs from objects.
                # The logic below IS the regrouping:
                # 1. survivor_flat + reserve -> active_indices
                # 2. rotate indices
                # 3. slice active_indices -> new_pairs, new_reserve
                # This seems correct for unrolled strategy as it operates on indices.
                
                survivor_flat = [idx for p in surviving_pairs for idx in p]
                active_indices = survivor_flat + [reserve_idx]
                
                apply_cyclic_rotation_indices(branch_qc, active_indices, self.k)
                
                new_active = active_indices 
                new_pairs = []
                for i in range(0, len(new_active) - 1, 2):
                    new_pairs.append([new_active[i], new_active[i+1]])
                new_reserve = new_active[-1]
                
                self._recurse(branch_qc, new_pairs, new_reserve, trial + 1, 
                              branch_conditions, total_meas_index + num_pairs, regs)
            else:
                self._finalize_path(branch_qc, branch_conditions, reserve_idx, regs)

    def _finalize_path(self, qc, conditions, reserve_idx, regs):
        final_qc = qc.copy()
        for i in range(self.k):
            r_qubits = final_qc.qubits[reserve_idx*self.k : (reserve_idx+1)*self.k]
            final_qc.measure(r_qubits[i], regs.cr_readout[i]) 
        
        self.circuits_data.append({
            'circuit': final_qc,
            'conditions': conditions,
            'metadata': {'type': 'unrolled', 'path_name': f"path_{len(self.circuits_data)}"}
        })
