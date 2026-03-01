#!/usr/bin/env python3
import os
import argparse
import numpy as np
import pandas as pd
from itertools import product
from concurrent.futures import ProcessPoolExecutor
from abc import ABC, abstractmethod

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error
from qiskit_aer.primitives import SamplerV2 as AerSampler

# ==========================================
# STRATEGY DEFINITION
# ==========================================

class QPAStrategy(ABC):
    def __init__(self, k, n_trials, n_registers=None):
        self.k = k
        self.n_trials = n_trials
        self.n_registers = n_registers if n_registers else 3

    @abstractmethod
    def build_circuit(self, epsilon):
        pass
    
    def apply_global_noise(self, qc, registers, epsilon):
        if epsilon <= 0: return
        noise = depolarizing_error(epsilon, self.k)
        for reg in registers:
            qc.append(noise, reg)

    def schur_test(self, qc, ctrl, res_bit, reg_a, reg_b):
        qc.reset(ctrl)
        qc.h(ctrl)
        for i in range(self.k):
            qc.cswap(ctrl, reg_a[i], reg_b[i])
        qc.h(ctrl)
        qc.measure(ctrl, res_bit)
        return res_bit

class HybridNRegStrategy(QPAStrategy):
    def __init__(self, k, n_trials, n_registers=5):
        assert n_registers % 2 == 1, "Number of registers must be odd (2i+1)."
        super().__init__(k, n_trials, n_registers)

    def build_circuit(self, epsilon):
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(self.n_registers)]
        max_parallel_tests = (self.n_registers - 1) // 2
        qr_ctrl_par = QuantumRegister(max_parallel_tests, "ctrl_par")
        qr_ctrl_rec = QuantumRegister(1, "ctrl_rec") 
        cr_pool = [ClassicalRegister(max_parallel_tests, f"res_t{t}") for t in range(self.n_trials)]
        cr_rec = ClassicalRegister(self.n_trials, "res_rec")
        cr_final = ClassicalRegister(self.k, "readout")
        
        regs = [*qr_data, qr_ctrl_par, qr_ctrl_rec, *cr_pool, cr_rec, cr_final]
        qc = QuantumCircuit(*regs)
        
        self.apply_global_noise(qc, qr_data, epsilon)
        
        initial_reserve = qr_data[-1]
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append((qr_data[i], qr_data[i+1]))
            
        self._build_recursive_layer(qc, initial_pairs, initial_reserve, 
                                    qr_ctrl_par, qr_ctrl_rec, 
                                    cr_pool, cr_rec, 0)
        
        qc.measure(initial_reserve, cr_final)
        return qc

    def _build_recursive_layer(self, qc, current_pairs, reserve_reg, 
                               qr_par, qr_rec, cr_pool, cr_rec, current_trial):
        if current_trial >= self.n_trials: return

        num_pairs = len(current_pairs)
        current_cr = cr_pool[current_trial]
        
        # 1. Parallel Schur Tests
        for i in range(num_pairs):
            self.schur_test(qc, qr_par[i], current_cr[i], current_pairs[i][0], current_pairs[i][1])

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
                    self.cyclic_rotation(qc, all_regs)
                    self._build_recursive_layer(qc, current_pairs, reserve_reg, 
                                                qr_par, qr_rec, cr_pool, cr_rec, current_trial + 1)
                
                # B. SOME FAILURE
                else:
                    surviving_pairs = []
                    for i, val in enumerate(outcome):
                        if val == 0: surviving_pairs.append(current_pairs[i])
                    
                    num_survivors = len(surviving_pairs)
                    if num_survivors > 1:
                        active_regs = []
                        for p in surviving_pairs: active_regs.extend(p)
                        active_regs.append(reserve_reg)
                        self.cyclic_rotation(qc, active_regs)
                        self._build_recursive_layer(qc, surviving_pairs, reserve_reg, 
                                                    qr_par, qr_rec, cr_pool, cr_rec, current_trial + 1)
                    elif num_survivors == 1:
                        kp1, kp2 = surviving_pairs[0]
                        self.run_swapnet_linear(qc, qr_rec, cr_rec, current_trial, kp1, kp2, reserve_reg)
                    else:
                        pass # All failed

            apply_conditions(conditions, logic_block)

    def cyclic_rotation(self, qc, regs):
        k = self.k
        N = len(regs)
        for i in range(k):
            for j in range(N-1, 0, -1):
                qc.swap(regs[j][i], regs[j-1][i])

    def run_swapnet_linear(self, qc, ctrl, cr_pool, start_t, r_keep1, r_keep2, r_reserve):
        remaining = self.n_trials - start_t
        for i in range(remaining):
            bit_idx = start_t + i
            if bit_idx >= self.n_trials: break
            for b in range(self.k): qc.swap(r_keep2[b], r_reserve[b])
            res = self.schur_test(qc, ctrl, cr_pool[bit_idx], r_keep1, r_keep2)
            with qc.if_test((res, 0)):
                for b in range(self.k): qc.swap(r_keep2[b], r_reserve[b])

# ==========================================
# WORKER FUNCTION (Single Data Point)
# ==========================================

def simulate_point(args_pack):
    """
    Independent worker to simulate one lambda value.
    This avoids GIL issues and allows full CPU utilization.
    """
    n, k, lam, trials, shots = args_pack
    
    # Re-instantiate strategy inside worker to avoid pickling complex objects
    strategy = HybridNRegStrategy(k, trials, n_registers=n)
    
    # Build
    qc = strategy.build_circuit(lam)
    
    # Transpile (Explicitly for AerSimulator to handle dynamic circuits)
    # Optimization level 1 is faster for large circuits like N=9
    qc = transpile(qc, AerSimulator(), optimization_level=1)
    
    # Run
    sampler = AerSampler()
    # SamplerV2 pubs: [(circuit,)]
    job = sampler.run([(qc,)], shots=shots)
    result = job.result()
    
    # Parse
    pub_result = result[0]
    # Check if readout exists (it should), handle potential no-measurement case
    if not hasattr(pub_result.data, 'readout'):
        return lam, 0.0
        
    counts = pub_result.data.readout.get_counts()
    
    # Target is '0' * k. Sampler returns bitstrings.
    # For k=2, target is '00'. In get_counts keys, look for '0'.
    # Note: Aer Sampler V2 behavior on bitstrings:
    # If using ClassicalRegister(size, name), get_counts returns bin strings.
    # We want the all-zeros state.
    
    target = '0' * k 
    # Actually, Sampler V2 usually returns '0' or '1' etc based on register value if simple?
    # Let's rely on standard count parsing.
    
    success = 0
    total = 0
    for key, count in counts.items():
        total += count
        # Simple check: if the key (bitstring) consists only of zeros
        if all(c == '0' for c in key):
            success += count
            
    return lam, success / total

# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, required=True, help="Number of registers (3, 5, 7, 9)")
    parser.add_argument('--k', type=int, default=2)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--shots', type=int, default=10000)
    parser.add_argument('--points', type=int, default=20, help="Number of lambda points")
    parser.add_argument('--workers', type=int, default=os.cpu_count(), help="Number of parallel processes")
    args = parser.parse_args()

    print(f"--- Starting Simulation: N={args.n}, k={args.k}, Workers={args.workers} ---")
    
    lambdas = np.linspace(0.0, 1.0, args.points)
    
    # Prepare arguments for parallel execution
    tasks = [(args.n, args.k, lam, args.trials, args.shots) for lam in lambdas]
    
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Use map to keep order, or as_completed. 
        # map is cleaner here as lambdas are sorted.
        for lam, fid in executor.map(simulate_point, tasks):
            print(f"   [N={args.n}] Lambda={lam:.2f} -> Fidelity={fid:.4f}")
            results.append((lam, fid))
            
    # Save Results
    df = pd.DataFrame(results, columns=['lambda', f'fidelity_n{args.n}'])
    output_dir = "results_hybrid_scaling"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"data_n{args.n}.csv")
    
    df.to_csv(output_file, index=False)
    print(f"[+] Saved results to {output_file}")

if __name__ == '__main__':
    main()