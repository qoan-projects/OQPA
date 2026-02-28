#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

def main():
    data_dir = "results_hybrid_scaling/k1_ntrials4"
    ns = [3, 5, 7, 9]
    dfs = {}
    
    # 1. Load Data
    print("Loading data...")
    try:
        for n in ns:
            filename = os.path.join(data_dir, f"data_n{n}.csv")
            dfs[n] = pd.read_csv(filename)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure the simulations have finished running.")
        return

    # 2. Create Merged CSV
    # Assume all use same lambda points (they should)
    merged_df = dfs[3][['lambda']].copy()
    for n in ns:
        # Rename column for clarity if needed, though they are likely named 'fidelity_n{n}' in file
        col_name = f'fidelity_n{n}'
        merged_df[col_name] = dfs[n][col_name]
    
    merged_output = os.path.join(data_dir, "hybrid_combined_n3_n5_n7_n9.csv")
    merged_df.to_csv(merged_output, index=False)
    print(f"Combined data saved to {merged_output}")

    # 3. Plot 1: Fidelity vs Lambda
    plt.figure(figsize=(10, 6))
    colors = {3: 'green', 5: 'crimson', 7: 'orange', 9: 'purple'}
    
    for n in ns:
        plt.plot(merged_df['lambda'], merged_df[f'fidelity_n{n}'], 
                 '-o', markersize=5, label=f'Hybrid N={n}', color=colors[n])
        
    plt.title('Hybrid QPA Performance vs Register Count (k=2)')
    plt.xlabel('Global Depolarizing Noise ($\lambda$)')
    plt.ylabel('Fidelity')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(data_dir, "plot_fidelity_vs_lambda.png"), dpi=300)
    print("Generated plot_fidelity_vs_lambda.png")

    # 4. Plot 2: Scaling Analysis (1-F vs N)
    # We choose specific lambda slices to analyze scaling
    target_lambdas = [0.1, 0.2, 0.3, 0.4]
    
    plt.figure(figsize=(10, 6))
    
    for lam_target in target_lambdas:
        # Find closest actual lambda in data
        closest_idx = (merged_df['lambda'] - lam_target).abs().idxmin()
        actual_lam = merged_df.loc[closest_idx, 'lambda']
        
        errors = []
        for n in ns:
            fid = merged_df.loc[closest_idx, f'fidelity_n{n}']
            errors.append(1 - fid)
            
        # Log-Log Plot
        plt.loglog(ns, errors, '-o', label=rf'$\lambda \approx {actual_lam:.2f}$')

        
        # Fit 1/N line for visual reference
        # Theoretical: Error ~ C * 1/N
        # On loglog: log(Err) = -1 * log(N) + C
        # We plot a reference line with slope -1 starting from the first point
        ref_y = [errors[0] * (ns[0] / x) for x in ns]
        plt.loglog(ns, ref_y, '--', color='gray', alpha=0.5, linewidth=1)

    plt.title('Error Scaling: Hybrid Strategy ($1-F$ vs $N$)')
    plt.xlabel('Number of Registers (N) [Log Scale]')
    plt.ylabel('Logical Error Rate ($1-F$) [Log Scale]')
    
    # Fake legend entry for the reference line
    plt.plot([], [], '--', color='gray', label='$\propto 1/N$ Reference')
    
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.savefig(os.path.join(data_dir, "plot_scaling_vs_n.png"), dpi=300)
    print("Generated plot_scaling_vs_n.png")

if __name__ == "__main__":
    main()