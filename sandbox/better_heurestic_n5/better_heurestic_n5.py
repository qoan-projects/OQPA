#!/usr/bin/env python3

import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from itertools import product
from tqdm import tqdm
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error
import qiskit.circuit.classical as qiskit_classical
from qiskit_aer.primitives import SamplerV2 as AerSampler
# ==========================================
# MODULE 1: ABSTRACT STRATEGY
# ==========================================

class QPAStrategy(ABC):
    def __init__(self, k, n_trials, n_registers=None):
        self.k = k
        self.n_trials = n_trials
        # Default to 3 if not specified, or allow override
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
        """Standard Schur test returning the raw Clbit."""
        qc.reset(ctrl)
        qc.h(ctrl)
        for i in range(self.k):
            qc.cswap(ctrl, reg_a[i], reg_b[i])
        qc.h(ctrl)
        qc.measure(ctrl, res_bit)
        return res_bit

# ==========================================
# MODULE 2: CYCLIC HYBRID STRATEGY (OLD)
# ==========================================
class HybridNRegStrategy(QPAStrategy):
    """
    Generalized Hybrid Strategy for N = 2i + 1 registers.
    Performs Cyclic Rotation on SURVIVORS + RESERVE.
    """
    def __init__(self, k, n_trials, n_registers=5):
        assert n_registers % 2 == 1, "Number of registers must be odd (2i+1)."
        super().__init__(k, n_trials, n_registers)

    def build_circuit(self, epsilon):
        # 1. Resources
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(self.n_registers)]
        
        max_parallel_tests = (self.n_registers - 1) // 2
        qr_ctrl_par = QuantumRegister(max_parallel_tests, "ctrl_par")
        qr_ctrl_rec = QuantumRegister(1, "ctrl_rec") 
        
        cr_pool = [ClassicalRegister(max_parallel_tests, f"res_t{t}") for t in range(self.n_trials)]
        cr_rec = ClassicalRegister(self.n_trials, "res_rec")
        cr_final = ClassicalRegister(self.k, "readout")
        
        regs = [*qr_data, qr_ctrl_par, qr_ctrl_rec, *cr_pool, cr_rec, cr_final]
        qc = QuantumCircuit(*regs)
        
        # 2. Noise
        self.apply_global_noise(qc, qr_data, epsilon)
        
        # 3. Recursive Logic
        initial_reserve = qr_data[-1]
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append((qr_data[i], qr_data[i+1]))
            
        self._build_recursive_layer(qc, initial_pairs, initial_reserve, 
                                    qr_ctrl_par, qr_ctrl_rec, 
                                    cr_pool, cr_rec, 
                                    current_trial=0)
        
        qc.measure(initial_reserve, cr_final)
        return qc

    def _build_recursive_layer(self, qc, current_pairs, reserve_reg, 
                               qr_par, qr_rec, cr_pool, cr_rec, 
                               current_trial):
        if current_trial >= self.n_trials:
            return

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
                if not cond_list:
                    block_func(); return
                head, *tail = cond_list
                with qc.if_test(head):
                    apply_conditions(tail, block_func)

            def logic_block():
                # A. ALL SUCCESS -> Cyclic Rotate & Recurse Same Size
                if all(v == 0 for v in outcome):
                    all_regs = []
                    for p in current_pairs: all_regs.extend(p)
                    all_regs.append(reserve_reg)
                    
                    self.cyclic_rotation(qc, all_regs)
                    
                    self._build_recursive_layer(qc, current_pairs, reserve_reg, 
                                                qr_par, qr_rec, cr_pool, cr_rec, 
                                                current_trial + 1)
                
                # B. SOME FAILURE -> Filter, ROTATE, & Reduce
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
                                                    qr_par, qr_rec, cr_pool, cr_rec, 
                                                    current_trial + 1)
                    
                    elif num_survivors == 1:
                        kp1, kp2 = surviving_pairs[0]
                        self.run_swapnet_linear(qc, qr_rec, cr_rec, current_trial, kp1, kp2, reserve_reg)
                    
                    else:
                        pass # All failed, return reserve (already in place)

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
# MODULE 3: NEW HEURISTIC STRATEGY (INFERENCE)
# ==========================================

class HeuristicDoubleCheckStrategy(QPAStrategy):
    """
    N=5 Heuristic with Inference (Corrected Logic).
    """
    def __init__(self, k, n_trials, n_registers=5):
        assert n_registers == 5, "N=5 specific."
        super().__init__(k, n_trials, n_registers)

    def build_circuit(self, epsilon):
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(5)]
        qr_ctrl = QuantumRegister(4, "ctrl")
        
        cr_trials = []
        for t in range(self.n_trials):
            cr_trials.append({
                'par': ClassicalRegister(2, f"t{t}_par"),
                'cross': ClassicalRegister(1, f"t{t}_cross"),
                'verify': ClassicalRegister(1, f"t{t}_verify")
            })
            
        cr_readout = ClassicalRegister(self.k, "readout")
        
        all_crs = []
        for cr_dict in cr_trials:
            all_crs.extend([cr_dict['par'], cr_dict['cross'], cr_dict['verify']])
        
        qc = QuantumCircuit(*qr_data, qr_ctrl, *all_crs, cr_readout)
        self.apply_global_noise(qc, qr_data, epsilon)
        
        self._heuristic_n5_layer(qc, qr_data, qr_ctrl, cr_trials, trial=0)
        
        qc.measure(qr_data[4], cr_readout)

        return qc

    def cyclic_rotation(self, qc, regs):
        k = self.k
        N = len(regs)
        for i in range(k):
            for j in range(N-1, 0, -1):
                qc.swap(regs[j][i], regs[j-1][i])

    def _heuristic_n5_layer(self, qc, regs, qr_ctrl, cr_trials, trial):
        if trial >= self.n_trials: return
        
        crs = cr_trials[trial]
        
        def swap_to_output(idx):
            if idx == 4: return
            for b in range(self.k):
                qc.swap(regs[idx][b], regs[4][b])

        # === 1. Parallel Tests ===
        # par[0] (LSB) = R1 vs R2
        self.schur_test(qc, qr_ctrl[0], crs['par'][0], regs[0], regs[1])
        # par[1] (MSB) = R3 vs R4
        self.schur_test(qc, qr_ctrl[1], crs['par'][1], regs[2], regs[3])

        # === PATH A: BOTH PASS (00 -> Value 0) ===
        with qc.if_test((crs['par'], 0)): 
            self.schur_test(qc, qr_ctrl[2], crs['cross'][0], regs[0], regs[2])
            
            # A1: Cross Pass
            with qc.if_test((crs['cross'], 0)):
                self.schur_test(qc, qr_ctrl[3], crs['verify'][0], regs[1], regs[3])
                
                # A11: Verify Pass
                with qc.if_test((crs['verify'], 0)):
                    self.cyclic_rotation(qc, regs)
                    self._heuristic_n5_layer(qc, regs, qr_ctrl, cr_trials, trial + 1)
                # A12: Verify Fail -> Return R5
                with qc.if_test((crs['verify'], 1)):
                    pass 

            # A2: Cross Fail
            with qc.if_test((crs['cross'], 1)):
                self.schur_test(qc, qr_ctrl[3], crs['verify'][0], regs[1], regs[4])
                
                # A21: Tie Pass -> Return R5
                with qc.if_test((crs['verify'], 0)):
                    pass 
                # A22: Tie Fail -> Return R4
                with qc.if_test((crs['verify'], 1)):
                    swap_to_output(3)

        # === PATH B: ONE PASSES ===
        
        # Case B1: (1,2) Pass, (3,4) Fail.
        # par[0]=0 (Pass), par[1]=1 (Fail) -> Binary 10 -> Value 2
        with qc.if_test((crs['par'], 2)): 
            # Survivors: R1, R2. Reserve: R5.
            # Manual Cyclic: [R1, R2, R5] -> [R5, R1, R2]
            for b in range(self.k):
                qc.swap(regs[1][b], regs[4][b])
                qc.swap(regs[0][b], regs[1][b])
            
            self._n3_cyclic_recursion(qc, regs, [0, 1, 4], qr_ctrl, cr_trials, trial + 1)

        # Case B2: (1,2) Fail, (3,4) Pass.
        # par[0]=1 (Fail), par[1]=0 (Pass) -> Binary 01 -> Value 1
        with qc.if_test((crs['par'], 1)):
            # Survivors: R3, R4. Reserve: R5.
            # Manual Cyclic: [R3, R4, R5] -> [R5, R3, R4]
            for b in range(self.k):
                qc.swap(regs[3][b], regs[4][b])
                qc.swap(regs[2][b], regs[3][b])
            
            self._n3_cyclic_recursion(qc, regs, [2, 3, 4], qr_ctrl, cr_trials, trial + 1)

        # === PATH C: BOTH FAIL (Value 3) ===
        with qc.if_test((crs['par'], 3)):
            pass 

    def _n3_cyclic_recursion(self, qc, all_regs, indices, qr_ctrl, cr_trials, trial):
        if trial >= self.n_trials: return
        
        rA, rB, rC = all_regs[indices[0]], all_regs[indices[1]], all_regs[indices[2]]
        crs = cr_trials[trial]
        
        self.schur_test(qc, qr_ctrl[0], crs['par'][0], rA, rB)
        
        with qc.if_test((crs['par'][0], 0)):
            for b in range(self.k):
                qc.swap(rB[b], rC[b])
                qc.swap(rA[b], rB[b])
            self._n3_cyclic_recursion(qc, all_regs, indices, qr_ctrl, cr_trials, trial + 1)
        
        with qc.if_test((crs['par'][0], 1)):
            if indices[2] != 4:
                for b in range(self.k):
                    qc.swap(rC[b], all_regs[4][b])

# ==========================================
# MODULE 4: EXECUTION ENGINE
# ==========================================

class QPASimulator:
    def __init__(self, k, shots=50000):
        self.k = k
        self.shots = shots
        self.sim = AerSimulator()
        self.sampler = AerSampler()
        self.target_str = '0' * k
        
    def run_sweep(self, strategy_class, lambdas, n_trials, desc, n_registers=3):
        fidelities = []
        # Instantiate strategy
        if strategy_class == HybridNRegStrategy:
            strategy = strategy_class(self.k, n_trials, n_registers)
        elif strategy_class == HeuristicDoubleCheckStrategy:
            strategy = strategy_class(self.k, n_trials, n_registers)
        else:
            strategy = strategy_class(self.k, n_trials)
        
        print(f"--- Simulating {desc} ---")
        
        for lam in tqdm(lambdas, leave=False):
            qc = strategy.build_circuit(lam)
            qc = transpile(qc, self.sim)
            job = self.sampler.run([(qc,)],shots = self.shots)
            result = job.result()
            pub_result = result[0]
            counts = pub_result.data.readout.get_counts()
            success = 0
            for bitstr, count in counts.items():
                val = bitstr.split()[0]
                if val == self.target_str:
                    success += count
            fidelities.append(success / self.shots)
            
        return fidelities




def run_logic_probe(strategy_class, n_trials=1):
    # 1. Setup
    strategy = strategy_class(k=1, n_trials=n_trials, n_registers=5)
    
    # 2. Build Circuit
    qc = strategy.build_circuit(epsilon=0.0)
    
    # 3. State Prep: |00110> 
    prep = QuantumCircuit(5)
    prep.x(2) # R3
    prep.x(3) # R4
    
    qc_combined = QuantumCircuit(*qc.qregs, *qc.cregs)
    
    # Compose logic (Prep must match qubit indices)
    qc_combined.compose(prep, range(5), inplace=True)
    qc_combined.compose(qc, inplace=True)
    
    # 4. Run with Sampler
    sampler = AerSampler()
    qc_combined = transpile(qc_combined, AerSimulator())
    
    # Sampler V2 requires a list of pubs [(circuit,)]
    job = sampler.run([(qc_combined,)],shots = 50000)
    result = job.result()
    
    # 5. Parse Results (Sampler V2 returns BitArrays)
    # Get the counts for the first (and only) pub result
    pub_result = result[0]
    counts = pub_result.data.readout.get_counts()
    
    success_count = counts.get('0', 0)
    total_shots = sum(counts.values())
    
    return success_count / total_shots

# ==========================================
# MAIN
# ==========================================

def get_exact_n3_theory(k, l):
    if k == 1: return (1/6) * (6 - l - 3*(l**2) + (l**3))
    elif k == 2: return (1/8) * (l - 2) * (l + 1) * (3*l - 4)
    elif k == 3: return (1/96) * (7*l - 8) * (7*(l**2) - 7*l - 12)
    elif k == 4: return (1/128) * (15*l - 16) * (5*(l**2) - 5*l - 8)
    else: d = 2**k; return 1 - (l * (1-1/d))**2 * 3

def get_exact_n5_theory_k2(l):
    # User provided polynomial for N=5, k=2
    term1 = (1/256) * ((4 - 3*l)**2) * (l**3)
    term2 = (5 * (l**3) * (3*l - 4) * (11*l - 16)) / 1024
    term3 = -(15 * (l**2) * (3*l - 4) * (32 + l * (13*l - 40))) / 1024
    term4 = -(9 * (l**2) * (3*l - 4) * (80 + l * (23*l - 88))) / 2560
    term5 = (l * (3*l - 4) * (-960 + l * (1648 + l * (211*l - 1004)))) / 1280
    term6 = -((3*l - 4) * (640 + l * (-1536 + l * (1440 + l * (99*l - 608))))) / 2560
    return term1 + term2 + term3 + term4 + term5 + term6

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=2)
    parser.add_argument('--trials', type=int, default=4)
    parser.add_argument('--shots', type=int, default=100000)
    args = parser.parse_args()
    
    simulator = QPASimulator(k=args.k, shots=args.shots)
    lambdas = np.linspace(0.0, 1.0, 20)
    
    # 1. Run New Heuristic (Inference) N=5
    # Note: This is a single-shot heuristic (depth determined by logic), so 'trials' param
    # mainly affects the Abstract init, but the logic is hardcoded 1-pass in build_circuit.
    fid_heuristic = simulator.run_sweep(HeuristicDoubleCheckStrategy, lambdas, args.trials, 
                                        f"Heuristic Inference (N=5)", n_registers=5)
    
    # 2. Run Hybrid Cyclic (N=5)
    fid_hybrid5 = simulator.run_sweep(HybridNRegStrategy, lambdas, args.trials, 
                                     f"Hybrid Cyclic (N=5)", n_registers=5)

    # 3. Run Hybrid Cyclic (N=3) - Baseline
    fid_hybrid3 = simulator.run_sweep(HybridNRegStrategy, lambdas, args.trials, 
                                     f"Hybrid Cyclic (N=3)", n_registers=3)

    # 4. Theory Curves
    d = 2**args.k
    fid_baseline = [1 - l * (1 - 1.0/d) for l in lambdas]
    fid_theory_3 = [get_exact_n3_theory(args.k, l) for l in lambdas]
    
    if args.k == 2:
        fid_theory_5 = [get_exact_n5_theory_k2(l) for l in lambdas]
    else:
        # Fallback approximation for k != 2
        fid_theory_5 = [1 - (l * (1-1/d))**3 * 5 for l in lambdas]

    # 5. Plotting
    plt.figure(figsize=(10, 7))
    
    # Experiments
    plt.plot(lambdas, fid_heuristic, '-o', color='purple', linewidth=2.5, label='Heuristic Inference (N=5)')
    plt.plot(lambdas, fid_hybrid5, '-s', color='crimson', linewidth=2, label='Hybrid Cyclic (N=5)')
    plt.plot(lambdas, fid_hybrid3, '-^', color='green', linewidth=2, label='Hybrid Cyclic (N=3)')
    
    # Theory
    plt.plot(lambdas, fid_baseline, '--', color='gray', alpha=0.6, label='Baseline (N=1)')
    plt.plot(lambdas, fid_theory_3, ':', color='blue', linewidth=2, label='Theory Optimal (N=3)')
    plt.plot(lambdas, fid_theory_5, ':', color='black', linewidth=2, label='Theory Optimal (N=5)')
    
    plt.title(f'N=5 Strategy Comparison: Inference vs Cyclic (k={args.k})')
    plt.xlabel('Global Depolarizing Noise ($\lambda$)')
    plt.ylabel('Fidelity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Save
    output_dir = "/home/caiosiq/OQPA-public/more_registers_qpa/results/better_heurestic_n5/"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'heuristic_comparison.png'))
    
    df = pd.DataFrame({
        'lambda': lambdas,
        'heuristic_n5': fid_heuristic,
        'cyclic_n5': fid_hybrid5,
        'cyclic_n3': fid_hybrid3,
        'theory_n3': fid_theory_3,
        'theory_n5': fid_theory_5
    })
    df.to_csv(os.path.join(output_dir, 'heuristic_data.csv'), index=False)
    print(f"\n[+] Results saved to {output_dir}")
    print('-------Testing Antisymmetry case -----------')
    print('N_trials=1')
    print('Results of Heurestic:', run_logic_probe(HeuristicDoubleCheckStrategy,n_trials=1))
    print('Results of Hybrid:', run_logic_probe(HybridNRegStrategy,n_trials=1))
    print('N_trials=2')
    print('Results of Heurestic:', run_logic_probe(HeuristicDoubleCheckStrategy,n_trials=2))
    print('Results of Hybrid:', run_logic_probe(HybridNRegStrategy,n_trials=2))
    print('N_trials=3')
    print('Results of Heurestic:', run_logic_probe(HeuristicDoubleCheckStrategy,n_trials=3))
    print('Results of Hybrid:', run_logic_probe(HybridNRegStrategy,n_trials=3))
if __name__ == '__main__':
    main()