
import sys
from core.strategies.unrolled import UnrolledStrategy
from core.hybrid_topology import UnrolledHybridStrategy
from core.noise_models import StandardDepolarizingStrategy

def compare_unrolled_circuits():
    print("--- Comparing UnrolledStrategy (New) vs UnrolledHybridStrategy (Old/Ref) ---")
    
    # Parameters
    n = 5
    k = 2
    trials = 3
    epsilon = 0.1
    
    # 1. New Strategy
    print("\n[1] Building New Strategy Circuits...")
    strategy = UnrolledStrategy(n_registers=n, k=k, n_trials=trials)
    noise_strat = StandardDepolarizingStrategy(k)
    strategy.set_noise_strategy(noise_strat)
    
    circuits_new = strategy.build(epsilon)
    print(f"New Strategy generated {len(circuits_new)} circuits.")
    
    # 2. Old Strategy
    print("\n[2] Building Old Strategy Circuits...")
    # UnrolledHybridStrategy in hybrid_topology.py matches the old structure
    old_strategy = UnrolledHybridStrategy(k=k, n_trials=trials, n_registers=n)
    # Old strategy takes noise strategy as arg to generate_all_paths
    circuits_old = old_strategy.generate_all_paths(epsilon, noise_strat)
    print(f"Old Strategy generated {len(circuits_old)} circuits.")
    
    # 3. Compare Count
    if len(circuits_new) == len(circuits_old):
        print("PASS: Circuit counts match.")
    else:
        print("FAIL: Circuit counts differ.")
        return

    # 4. Compare First Circuit
    print("\n--- Comparing First Circuit ---")
    qc_new = circuits_new[0]['circuit']
    qc_old = circuits_old[0]['circuit']
    
    print(f"New Depth: {qc_new.depth()}, Ops: {qc_new.count_ops()}")
    print(f"Old Depth: {qc_old.depth()}, Ops: {qc_old.count_ops()}")
    
    # Check Reset
    if 'reset' in qc_new.count_ops():
        print(f"New Circuit has {qc_new.count_ops()['reset']} resets.")
    else:
        print("New Circuit has NO resets.")
        
    if 'reset' in qc_old.count_ops():
        print(f"Old Circuit has {qc_old.count_ops()['reset']} resets.")
    else:
        print("Old Circuit has NO resets.")
        
    # Compare Last Circuit (Deepest path?)
    print("\n--- Comparing Last Circuit ---")
    qc_new_last = circuits_new[-1]['circuit']
    qc_old_last = circuits_old[-1]['circuit']
    
    print(f"New Last Depth: {qc_new_last.depth()}, Ops: {qc_new_last.count_ops()}")
    print(f"Old Last Depth: {qc_old_last.depth()}, Ops: {qc_old_last.count_ops()}")

if __name__ == "__main__":
    compare_unrolled_circuits()
