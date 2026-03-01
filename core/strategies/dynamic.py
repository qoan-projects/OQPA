from typing import List, Dict, Any
from itertools import product
from qiskit import QuantumCircuit
from core.strategies.base import CircuitGenerationStrategy
from core.registers import QPARegisters
from core.ops import apply_schur_test, apply_cyclic_rotation

class DynamicStrategy(CircuitGenerationStrategy):
    """
    Builds a single dynamic circuit (using if_test) for AER simulation.
    """
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        regs = QPARegisters(self.n_registers, self.k, self.n_trials, use_ancilla_pool=False)
        qc = QuantumCircuit(*regs.get_circuit_registers())
        
        # Apply Noise
        if self.noise_strategy and epsilon > 0:
            self.noise_strategy.apply_noise(qc, regs.qr_data, epsilon)
        
        initial_reserve = regs.get_reserve()
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append((regs.get_data_register(i), regs.get_data_register(i+1)))
            
        self._build_recursive_layer(qc, initial_pairs, initial_reserve, regs, 0)
        
        qc.measure(initial_reserve, regs.cr_readout)
        
        return [{'circuit': qc, 'conditions': {}, 'metadata': {'type': 'dynamic'}}]

    def _build_recursive_layer(self, qc, current_pairs, reserve_reg, regs: QPARegisters, current_trial):
        if current_trial >= self.n_trials: return

        num_pairs = len(current_pairs)
        current_cr = regs.cr_pool[current_trial]
        qr_par = regs.qr_ctrl_par
        
        # 1. Parallel Schur Tests
        for i in range(num_pairs):
            apply_schur_test(qc, qr_par[i], current_pairs[i][0], current_pairs[i][1], self.k)
            qc.measure(qr_par[i], current_cr[i])
            qc.reset(qr_par[i])

        # 2. Branching Logic
        outcomes = list(product([0, 1], repeat=num_pairs))
        
        for outcome in outcomes:
            conditions = [(current_cr[i], val) for i, val in enumerate(outcome)]
            
            def apply_conditions(cond_list, block_func):
                if not cond_list: block_func(); return
                head, *tail = cond_list
                with qc.if_test(head): apply_conditions(tail, block_func)

            def logic_block():
                # A. ALL SUCCESS
                if all(v == 0 for v in outcome):
                    all_regs = []
                    for p in current_pairs: all_regs.extend(p)
                    all_regs.append(reserve_reg)
                    
                    apply_cyclic_rotation(qc, all_regs, self.k)
                    
                    self._build_recursive_layer(qc, current_pairs, reserve_reg, regs, current_trial + 1)
                
                # B. SOME FAILURE
                else:
                    surviving_pairs = []
                    for i, val in enumerate(outcome):
                        if val == 0: surviving_pairs.append(current_pairs[i])
                    
                    num_survivors = len(surviving_pairs)
                    if num_survivors >= 1:
                        active_regs = []
                        for p in surviving_pairs: active_regs.extend(p)
                        active_regs.append(reserve_reg)
                        
                        apply_cyclic_rotation(qc, active_regs, self.k)
                        
                        # Reconstruct pairs from the active registers
                        # (Logic matches CircuitBuilder's implicit behavior)
                        new_pairs = []
                        for i in range(0, len(active_regs) - 1, 2):
                            new_pairs.append((active_regs[i], active_regs[i+1]))
                        new_reserve = active_regs[-1]
                        
                        self._build_recursive_layer(qc, new_pairs, new_reserve, regs, current_trial + 1)
                    else:
                        pass # All failed

            apply_conditions(conditions, logic_block)
