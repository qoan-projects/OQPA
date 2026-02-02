#!/usr/bin/env python3

import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from itertools import product
from tqdm import tqdm
from abc import ABC, abstractmethod

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error
import qiskit.circuit.classical as qiskit_classical
import qiskit.quantum_info as qi



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
# MODULE 2: CONCRETE STRATEGIES
# ==========================================
class HybridNRegStrategy(QPAStrategy):
    """
    Generalized Hybrid Strategy for N = 2i + 1 registers.
    Now performs Cyclic Rotation on SURVIVORS + RESERVE even in partial success cases.
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
            # Build nested if_test conditions
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
                        # [FIX]: Gather survivors + reserve and ROTATE
                        # This mixes the 'Best Guess' (Reserve) with the 'Fresh Survivors'
                        active_regs = []
                        for p in surviving_pairs: active_regs.extend(p)
                        active_regs.append(reserve_reg)
                        
                        self.cyclic_rotation(qc, active_regs)
                        
                        # Recurse with the rotated registers
                        # Note: Register objects are the same, but their contents have shifted.
                        # The last register in 'surviving_pairs' now holds the Old Reserve.
                        self._build_recursive_layer(qc, surviving_pairs, reserve_reg, 
                                                    qr_par, qr_rec, cr_pool, cr_rec, 
                                                    current_trial + 1)
                    
                    elif num_survivors == 1:
                        # SwapNet (3-Reg) Fallback
                        kp1, kp2 = surviving_pairs[0]
                        self.run_swapnet_linear(qc, qr_rec, cr_rec, current_trial, kp1, kp2, reserve_reg)
                    
                    else:
                        pass # All failed, stop.

            apply_conditions(conditions, logic_block)

    def cyclic_rotation(self, qc, regs):
        # [R1, R2... RN] -> [RN, R1... RN-1]
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


class BaseSwapNetStrategy(QPAStrategy):
    """
    Standard Base Comparison: 3 Registers.
    Recursive implementation to prevent gate collisions on failure branches.
    
    Logic:
    1. Test R1 vs R2.
    2. If Fail: Stop (Return R3).
    3. If Success: 
       - Swap R2 <-> R3 (Bring reserve in).
       - Recurse to next trial.
       - Swap Back if the recursion (next trial) succeeds? 
         No, the logic is linear: Swap In -> Test -> If Success, Swap Back.
         
    Actually, the recursive structure for a linear chain is:
    Trial T:
      Swap(R2, R3)
      Result = Schur(R1, R2)
      If Result == Success:
          Swap(R2, R3)  # Restore the good state to R3
          Recurse(Trial T+1) # Continue trying to purify
      Else:
          # Stop. R3 holds the "pre-swap" good state? 
          # Wait, we swapped R2(bad/unknown) into R3(reserve).
          # If Schur fails, R3 now holds the bad state!
          # We MUST Swap Back in the Else branch (or unconditionally before the check)?
          
          # Let's trace the standard SwapNet logic carefully:
          # "Swap R2 and R3, perform Schur on 1 and 2... if we fail, just return 3."
          
          # If we swap R2<->R3, then R3 holds the old R2 (garbage), and R2 holds the Reserve.
          # We test R1 vs R2 (Reserve).
          # If Fail: The Reserve (now in R2) was bad/mismatched. 
          # The "Safest" state is actually... well, if the test fails, both inputs are likely bad.
          # But in the user's logic: "If we fail... just return 3."
          
          # If we fail, R3 currently holds the old R2.
          # If we succeed, we swap back, so R3 holds the Reserve (verified).
    """

    def build_circuit(self, epsilon):
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(3)]
        qr_ctrl = QuantumRegister(1, "ctrl")
        cr_tests = ClassicalRegister(self.n_trials + 1, "res_tests") # +1 for initial test
        cr_final = ClassicalRegister(self.k, "readout")
        
        qc = QuantumCircuit(*qr_data, qr_ctrl, cr_tests, cr_final)
        self.apply_global_noise(qc, qr_data, epsilon)
        
        # 1. Initial Test: R1 vs R2
        # This is outside the recursion because it establishes the first "Winner"
        res_0 = self.schur_test(qc, qr_ctrl[0], cr_tests[0], qr_data[0], qr_data[1])
        
        # Branching: Only proceed if Initial Test passed
        def initial_success_block():
            # Keepers: R1, R2. Reserve: R3.
            # Start recursion for the refinement trials
            self._build_recursive_swapnet(qc, qr_data, qr_ctrl, cr_tests, current_trial=1)
            
        with qc.if_test((res_0, 0)):
            initial_success_block()
        
        # 3. Final Readout
        # In SwapNet, R3 (Register 3) is the designated output (Reserve)
        qc.measure(qr_data[2], cr_final)
        return qc

    def _build_recursive_swapnet(self, qc, regs, qr_ctrl, cr_tests, current_trial):
        """
        Recursively builds the linear SwapNet chain.
        """
        # Base Case: Stop if max trials reached
        if current_trial > self.n_trials:
            return

        r1, r2, r3 = regs[0], regs[1], regs[2]
        
        # 1. Swap R2 <-> R3 (Bring Reserve into testing position)
        for b in range(self.k): qc.swap(r2[b], r3[b])
        
        # 2. Schur Test R1 vs R2 (which is the Reserve)
        res = self.schur_test(qc, qr_ctrl[0], cr_tests[current_trial], r1, r2)
        
        # 3. Branching Logic
        # Case A: Success (0) -> Swap Back & Continue
        def success_block():
            # Swap Back (Restore verified state to R3)
            for b in range(self.k): qc.swap(r2[b], r3[b])
            
            # Recurse: Try to improve further
            self._build_recursive_swapnet(qc, regs, qr_ctrl, cr_tests, current_trial + 1)
            
        # Case B: Failure (1) -> Stop.
        # Note: If we fail, R3 currently holds the 'Old R2' (which was a previous winner).
        # R2 holds the 'Reserve' which just failed.
        # The user says "return 3". R3 holds the previous winner. This is correct.
        # We do NOT swap back.
        
        with qc.if_test((res, 0)):
            success_block()

# ==========================================
# MODULE 3: EXECUTION ENGINE
# ==========================================

class QPASimulator:
    def __init__(self, k, shots=5000):
        self.k = k
        self.shots = shots
        self.sim = AerSimulator()
        self.target_str = '0' * k

    def run_sweep(self, strategy_class, lambdas, n_trials, desc, n_registers=3):
        fidelities = []
        # Instantiate strategy (pass n_registers only if supported)
        if strategy_class == HybridNRegStrategy:
            strategy = strategy_class(self.k, n_trials, n_registers)
        else:
            strategy = strategy_class(self.k, n_trials)
        
        print(f"--- Simulating {desc} ---")
        
        for lam in tqdm(lambdas, leave=False):
            qc = strategy.build_circuit(lam)
            qc = transpile(qc, self.sim)
            result = self.sim.run(qc, shots=self.shots).result()
            counts = result.get_counts()
            
            success = 0
            for bitstr, count in counts.items():
                val = bitstr.split()[0]
                if val == self.target_str:
                    success += count
            fidelities.append(success / self.shots)
            
        return fidelities

# ==========================================
# MAIN
# ==========================================

def get_exact_n3_theory(k, l):
    """
    Returns the exact theoretical max fidelity for N=3 copies 
    under Global Depolarizing noise (lambda = l).
    Formulas provided by user.
    """
    if k == 1:
        # 1/6 (6 - l - 3l^2 + l^3)
        return (1/6) * (6 - l - 3*(l**2) + (l**3))
    elif k == 2:
        # 1/8 (-2 + l) (1 + l) (-4 + 3l)
        # Let's expand or use as is: 1/8 * (l - 2) * (l + 1) * (3*l - 4)
        return (1/8) * (l - 2) * (l + 1) * (3*l - 4)
    elif k == 3:
        # 1/96 (-8 + 7l) (-12 + 7(-1 + l)l)
        # Inner term: -12 + 7*(l^2 - l) = 7l^2 - 7l - 12
        return (1/96) * (7*l - 8) * (7*(l**2) - 7*l - 12)
    elif k == 4:
        # 1/128 (-16 + 15l) (-8 + 5(-1 + l)l)
        # Inner term: -8 + 5*(l^2 - l) = 5l^2 - 5l - 8
        return (1/128) * (15*l - 16) * (5*(l**2) - 5*l - 8)
    else:
        # Fallback for k > 4 (Use the d-dimensional approx)
        d = 2**k
        # Standard approx for N=3 is F ~ F_in + O(gain)
        return 1 - (l * (1-1/d))**2 * 3
def get_exact_n5_theory_k2(l):
    """
    Returns the exact theoretical max fidelity for N=5 copies 
    specifically for k=2 (2 qubits), based on the provided polynomial list.
    """
    # Term 1
    term1 = (1/256) * ((4 - 3*l)**2) * (l**3)
    
    # Term 2
    term2 = (5 * (l**3) * (3*l - 4) * (11*l - 16)) / 1024
    
    # Term 3
    term3 = -(15 * (l**2) * (3*l - 4) * (32 + l * (13*l - 40))) / 1024
    
    # Term 4
    term4 = -(9 * (l**2) * (3*l - 4) * (80 + l * (23*l - 88))) / 2560
    
    # Term 5
    # Inner: -960 + l*(1648 + l*(-1004 + 211*l))
    term5 = (l * (3*l - 4) * (-960 + l * (1648 + l * (211*l - 1004)))) / 1280
    
    # Term 6
    # Inner: 640 + l*(-1536 + l*(1440 + l*(-608 + 99*l)))
    term6 = -((3*l - 4) * (640 + l * (-1536 + l * (1440 + l * (99*l - 608))))) / 2560
    
    return term1 + term2 + term3 + term4 + term5 + term6
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=2)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--shots', type=int, default=10000)
    args = parser.parse_args()
    
    # 1. Setup
    simulator = QPASimulator(k=args.k, shots=args.shots)
    lambdas = np.linspace(0.0, 1.0, 20)
    
    # 2. Run Hybrid Strategy (5 Registers)
    fid_7hybrid = simulator.run_sweep(HybridNRegStrategy, lambdas, args.trials, 
                                     f"Hybrid {7}-Reg_new", n_registers=7)
    fid_5hybrid = simulator.run_sweep(HybridNRegStrategy, lambdas, args.trials, 
                                     f"Hybrid {5}-Reg_new", n_registers=5)
    fid_3hybrid = simulator.run_sweep(HybridNRegStrategy, lambdas, args.trials, 
                                     f"Hybrid {3}-Reg_new", n_registers=3)
    # 3. Run Base Strategy (3 Registers)
    fid_base = simulator.run_sweep(BaseSwapNetStrategy, lambdas, args.trials, "Base SwapNet 3-Reg")
    
    # 4. Calculate Theoretical Limits
    d = 2**args.k
    
    # A. Baseline (Do Nothing, N=1)
    # F = 1 - lambda * (1 - 1/d)
    fid_baseline = [1 - l * (1 - 1.0/d) for l in lambdas]
    
    # B. Theoretical Max N=3 (Optimal QPA)
    # Uses the exact polynomials you provided
    fid_theory_3 = [get_exact_n3_theory(args.k, l) for l in lambdas]
    fid_theory_5 = [get_exact_n5_theory_k2(l) for l in lambdas]
    
    # C. Theoretical Max N=5 (Approx)
    # Since we don't have the exact polynomial for N=5, we use the scaling law.
    # N=5 should suppress error roughly by epsilon^3 (since N=3 does epsilon^2).
    # We use a visual guide to show the ceiling.
    # Logic: Error_out ~ C * (Error_in)^(N/2 + 0.5) roughly
    # fid_theory_5 = [1 - (l * (1-1/d))**3 * 5 for l in lambdas] # Visual proxy
    # fid_theory_5 = [max(f, 1/d) for f in fid_theory_5] # Clamp to random guess

    # 5. Plotting
    plt.figure(figsize=(10, 7))
    
    # Experimental Data
    plt.plot(lambdas, fid_7hybrid, '-o', color='orange', linewidth=2, label=f'General Hybrid Gamble (N=7, trials = {args.trials})')
    plt.plot(lambdas, fid_5hybrid, '-o', color='crimson', linewidth=2, label=f'Hybrid Gamble (N=5, trials = {args.trials})')
    plt.plot(lambdas, fid_3hybrid, '-o', color='green', linewidth=2, label=f'Hybrid Gamble (N=3, trials = {args.trials})')
    # plt.plot(lambdas, fid_base, '-s', color='navy', linewidth=2, label=f'Base SwapNet (N=3, trials = {args.trials})')
    
    # Baselines and Limits
    plt.plot(lambdas, fid_baseline, '--', color='gray', alpha=0.7, label='Do Nothing (N=1)')
    
    # Exact Theory N=3
    # plt.plot(lambdas, fid_theory_3, ':', color='blue', linewidth=2, label='Optimal QPA (N=3, Exact)')
    plt.plot(lambdas, fid_theory_5, ':', color='blue', linewidth=2, label='Optimal QPA (N=5, Exact)')
    
    # Approx Theory N=5
    # plt.plot(lambdas, fid_theory_5, ':', color='red', alpha=0.5, label='Optimal QPA (N=5, Est.)')
    
    plt.title(f'QPA Strategy Comparison (k={args.k}, Trials={args.trials})')
    plt.xlabel('Global Depolarizing Noise ($\lambda$)')
    plt.ylabel('Fidelity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Save
    output_dir = "/home/caiosiq/OQPA-public/more_registers_qpa/results/"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'strategy_comparison.png'))
    
    df = pd.DataFrame({
        'lambda': lambdas,
        'hybrid_5reg': fid_5hybrid,
        'hybrid_7reg': fid_7hybrid,
        'base_3reg': fid_base,
        'baseline': fid_baseline,
        'theory_3': fid_theory_3,
        'theory_5': fid_theory_5
    })
    df.to_csv(os.path.join(output_dir, 'comparison_data.csv'), index=False)
    print(f"\n[+] Done. Results saved to {output_dir} directory.")

if __name__ == '__main__':
    main()