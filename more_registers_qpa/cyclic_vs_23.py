#!/usr/bin/env python3

import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
from abc import ABC, abstractmethod

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error

# ==========================================
# MODULE 1: ABSTRACT STRATEGY
# ==========================================

class QPAStrategy(ABC):
    def __init__(self, k, n_trials):
        self.k = k
        self.n_trials = n_trials

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
# MODULE 2: THE VARIATION STRATEGIES
# ==========================================

class SwapNetVariation(QPAStrategy):
    """
    Implements N=3 SwapNet with selectable permutation logic.
    mode='standard': Swap R2 <-> R3 (Standard SwapNet)
    mode='cyclic':   Rotate R1->R2->R3->R1 (Cyclic)
    """
    def __init__(self, k, n_trials, mode='standard'):
        super().__init__(k, n_trials)
        assert mode in ['standard', 'cyclic'], "Mode must be 'standard' or 'cyclic'"
        self.mode = mode

    def build_circuit(self, epsilon):
        # Registers: 3 Data, 1 Control
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(3)]
        qr_ctrl = QuantumRegister(1, "ctrl")
        
        # Bits: 1 for Initial Test, n_trials for Loop
        cr_tests = ClassicalRegister(self.n_trials + 1, "res_tests") 
        cr_final = ClassicalRegister(self.k, "readout")
        
        qc = QuantumCircuit(*qr_data, qr_ctrl, cr_tests, cr_final)
        
        # 1. Apply Noise
        self.apply_global_noise(qc, qr_data, epsilon)
        
        # 2. Initial Test: R1 vs R2
        # If this fails (Anti-Sym), we stop immediately (or output R3).
        # Standard SwapNet logic usually assumes we start with a success or just filters.
        # Here we follow the recursive logic: Test -> If Success -> Enter Loop.
        
        res_0 = self.schur_test(qc, qr_ctrl[0], cr_tests[0], qr_data[0], qr_data[1])
        
        # Define the Recursion
        self._build_recursive_step(qc, qr_data, qr_ctrl, cr_tests, current_trial=1)
        
        # 3. Readout
        # Standard SwapNet reads out R3 (The Reserve)
        # Cyclic: We also read out R3 for consistency, as it was the "safe" register initially.
        qc.measure(qr_data[2], cr_final)
        return qc

    def _build_recursive_step(self, qc, regs, qr_ctrl, cr_tests, current_trial):
        # Unpack registers for clarity
        r1, r2, r3 = regs[0], regs[1], regs[2]
        current_bit = cr_tests[current_trial - 1] # The result of the PREVIOUS test
        
        if current_trial > self.n_trials:
            return

        def loop_body():
            # A. PERMUTATION STEP
            if self.mode == 'standard':
                # Swap R2 <-> R3
                for b in range(self.k): qc.swap(r2[b], r3[b])
            
            elif self.mode == 'cyclic':
                # Cyclic Rotate: R1->R2, R2->R3, R3->R1
                # Implementation: Swap(1,2) then Swap(2,3) performs 1->2->3->1 ?
                # Let's trace: [A, B, C]
                # Swap(1,2) -> [B, A, C]
                # Swap(2,3) -> [B, C, A]
                # Result: Old R1 is at 3. Old R2 is at 1. Old R3 is at 2.
                # Yes, this is a cyclic shift.
                for b in range(self.k): 
                    qc.swap(r1[b], r2[b])
                    qc.swap(r2[b], r3[b])

            # B. TEST STEP
            # We always test R1 vs R2 in the new configuration
            # (Note: In Cyclic, R1 is now holding the old R2 or R3)
            new_res = self.schur_test(qc, qr_ctrl[0], cr_tests[current_trial], r1, r2)
            
            # C. RECURSION
            # Only continue if THIS test was also a Success (0)
            with qc.if_test((new_res, 0)):
                self._build_recursive_step(qc, regs, qr_ctrl, cr_tests, current_trial + 1)
        
        # Only execute this step if the PREVIOUS test was Success (0)
        with qc.if_test((current_bit, 0)):
            loop_body()

# ==========================================
# MODULE 3: SIMULATION & PLOTTING
# ==========================================

class QPASimulator:
    def __init__(self, k, shots=5000):
        self.k = k
        self.shots = shots
        self.sim = AerSimulator()
        self.target_str = '0' * k

    def run_sweep(self, strategy_obj, lambdas, desc):
        fidelities = []
        print(f"--- Simulating {desc} ---")
        
        for lam in tqdm(lambdas, leave=False):
            qc = strategy_obj.build_circuit(lam)
            qc = transpile(qc, self.sim)
            result = self.sim.run(qc, shots=self.shots).result()
            counts = result.get_counts()
            
            success = 0
            for bitstr, count in counts.items():
                val = bitstr.split()[0] # Readout is the first register in the bitstring
                if val == self.target_str:
                    success += count
            fidelities.append(success / self.shots)
            
        return fidelities

def get_exact_n3_theory(k, l):
    # exact N=3 formula for k=2
    return (1/8) * (l - 2) * (l + 1) * (3*l - 4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=2)
    parser.add_argument('--trials', type=int, default=4)
    parser.add_argument('--shots', type=int, default=500000)
    args = parser.parse_args()
    
    simulator = QPASimulator(k=args.k, shots=args.shots)
    lambdas = np.linspace(0.0, 1.0, 15)
    
    # 1. Instantiate Strategies
    strat_standard = SwapNetVariation(args.k, args.trials, mode='standard')
    strat_cyclic   = SwapNetVariation(args.k, args.trials, mode='cyclic')
    
    # 2. Run Simulations
    fid_standard = simulator.run_sweep(strat_standard, lambdas, "Standard SwapNet (Swap 2-3)")
    fid_cyclic   = simulator.run_sweep(strat_cyclic,   lambdas, "Cyclic SwapNet (Rot 1-2-3)")
    
    # 3. Theory Curves
    # N=3 Optimal
    fid_theory_3 = [get_exact_n3_theory(args.k, l) for l in lambdas]
    
    # Baseline (N=1)
    d = 2**args.k
    fid_baseline = [1 - l * (1 - 1.0/d) for l in lambdas]

    # 4. Plotting
    plt.figure(figsize=(10, 7))
    
    plt.plot(lambdas, fid_theory_3, ':', color='black', linewidth=2, label='Optimal QPA Theory (N=3)')
    plt.plot(lambdas, fid_standard, '-o', color='blue', label='Standard SwapNet (Swap 2<->3)')
    plt.plot(lambdas, fid_cyclic,   '-^', color='red',  label='Cyclic Rotation (1->2->3)')
    plt.plot(lambdas, fid_baseline, '--', color='gray', alpha=0.5, label='Baseline (No QPA)')

    plt.title(f'Permutation Strategy Analysis (N=3, k={args.k}, Depth={args.trials})')
    plt.xlabel('Depolarizing Noise ($\lambda$)')
    plt.ylabel('Output Fidelity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    output_dir = "/home/caiosiq/OQPA-public/more_registers_qpa/results/"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'cyclic_vs_standard.png')
    plt.savefig(output_path)
    print(f"Saved plot to {output_path}")

if __name__ == '__main__':
    main()