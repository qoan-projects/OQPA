import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os

# Set academic style
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.size": 14,
    "axes.labelsize": 16,
    "axes.titlesize": 18,
    "legend.fontsize": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "figure.figsize": (8, 6),
    "lines.linewidth": 2,
    "lines.markersize": 8,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

def get_theoretical_fidelity(n, k, r, lam):
    """
    Returns the theoretical fidelity F(lambda) based on n, k, and r (trials).
    """
    if k == 1 and r == 3:
        if n == 3:
            # 1/128 (2 (-1 + \[Lambda]) - \[Lambda]) (-21 (-1 + \[Lambda]) \[Lambda] + 2 (-32 - 21 \[Lambda] + 21 \[Lambda]^2))
            term1 = (1/128) * (2*(-1 + lam) - lam)
            term2 = (-21*(-1 + lam)*lam + 2*(-32 - 21*lam + 21*lam**2))
            return term1 * term2
        elif n == 5:
            # -(((2 (-1 + \[Lambda]) - \[Lambda]) (33 (-1 + \[Lambda]) \[Lambda]^3 + 2 \[Lambda]^2 (239 - 456 \[Lambda] + 217 \[Lambda]^2) - 16 \[Lambda] (100 + 76 \[Lambda] - 315 \[Lambda]^2 + 139 \[Lambda]^3) + 8 (512 + 400 \[Lambda] + 65 \[Lambda]^2 - 771 \[Lambda]^3 + 306 \[Lambda]^4)))/8192)
            term1 = (2*(-1 + lam) - lam)
            term2 = (33*(-1 + lam)*(lam**3) 
                     + 2*(lam**2)*(239 - 456*lam + 217*(lam**2))
                     - 16*lam*(100 + 76*lam - 315*(lam**2) + 139*(lam**3))
                     + 8*(512 + 400*lam + 65*(lam**2) - 771*(lam**3) + 306*(lam**4)))
            return -(term1 * term2) / 8192
        elif n == 7:
            # 1/524288(2 (-1 + \[Lambda]) - \[Lambda]) (307 (-1 + \[Lambda]) \[Lambda]^5 + ...
            term1 = (2*(-1 + lam) - lam)
            term2 = (307*(-1 + lam)*(lam**5)
                     + 2*(lam**4)*(-2166 + 3479*lam - 1313*(lam**2))
                     + 4*(lam**3)*(1757 - 3681*lam + 3875*(lam**2) - 1951*(lam**3))
                     + 8*(lam**2)*(-5856 - 1031*lam + 31393*(lam**2) - 36099*(lam**3) + 11593*(lam**4))
                     + 16*lam*(6656 + 9472*lam - 6181*(lam**2) - 45641*(lam**3) + 49393*(lam**4) - 13699*(lam**5))
                     + 32*(-8192 - 6656*lam - 3616*(lam**2) + 5455*(lam**3) + 20095*(lam**4) - 20341*(lam**5) + 5063*(lam**6)))
            return (1/524288) * term1 * term2

    elif k == 2 and r == 3:
        if n == 3:
            # 1/512 (4 (-1 + \[Lambda]) - \[Lambda]) (-21 (-1 + \[Lambda]) \[Lambda] + 4 (-32 - 21 \[Lambda] + 21 \[Lambda]^2))
            term1 = (1/512) * (4*(-1 + lam) - lam)
            term2 = (-21*(-1 + lam)*lam + 4*(-32 - 21*lam + 21*(lam**2)))
            return term1 * term2
        elif n == 5:
            # -(((4 (-1 + \[Lambda]) - \[Lambda]) (33 (-1 + \[Lambda]) \[Lambda]^3 + 4 \[Lambda]^2 (239 - 456 \[Lambda] + 217 \[Lambda]^2) - 64 \[Lambda] (100 + 76 \[Lambda] - 315 \[Lambda]^2 + 139 \[Lambda]^3) + 64 (512 + 400 \[Lambda] + 65 \[Lambda]^2 - 771 \[Lambda]^3 + 306 \[Lambda]^4)))/131072)
            term1 = (4*(-1 + lam) - lam)
            term2 = (33*(-1 + lam)*(lam**3)
                     + 4*(lam**2)*(239 - 456*lam + 217*(lam**2))
                     - 64*lam*(100 + 76*lam - 315*(lam**2) + 139*(lam**3))
                     + 64*(512 + 400*lam + 65*(lam**2) - 771*(lam**3) + 306*(lam**4)))
            return -(term1 * term2) / 131072
        elif n == 7:
            # 1/33554432(4 (-1 + \[Lambda]) - \[Lambda]) (307 (-1 + \[Lambda]) \[Lambda]^5 + ...
            term1 = (4*(-1 + lam) - lam)
            term2 = (307*(-1 + lam)*(lam**5)
                     + 4*(lam**4)*(-2166 + 3479*lam - 1313*(lam**2))
                     + 16*(lam**3)*(1757 - 3681*lam + 3875*(lam**2) - 1951*(lam**3))
                     + 64*(lam**2)*(-5856 - 1031*lam + 31393*(lam**2) - 36099*(lam**3) + 11593*(lam**4))
                     + 256*lam*(6656 + 9472*lam - 6181*(lam**2) - 45641*(lam**3) + 49393*(lam**4) - 13699*(lam**5))
                     + 1024*(-8192 - 6656*lam - 3616*(lam**2) + 5455*(lam**3) + 20095*(lam**4) - 20341*(lam**5) + 5063*(lam**6)))
            return (1/33554432) * term1 * term2
            
    elif k == 1 and r == 4:
        if n == 3:
            # 1/512 (2 (-1 + \[Lambda]) - \[Lambda]) (-85 (-1 + \[Lambda]) \[Lambda] + 2 (-128 - 85 \[Lambda] + 85 \[Lambda]^2))
            term1 = (1/512) * (2*(-1 + lam) - lam)
            term2 = (-85*(-1 + lam)*lam + 2*(-128 - 85*lam + 85*(lam**2)))
            return term1 * term2
        elif n == 5:
            # -(((2 (-1 + \[Lambda]) - \[Lambda]) (433 (-1 + \[Lambda]) \[Lambda]^3 + 2 \[Lambda]^2 (3919 - 7780 \[Lambda] + 3861 \[Lambda]^2) - 8 \[Lambda] (3264 + 2596 \[Lambda] - 10595 \[Lambda]^2 + 4735 \[Lambda]^3) + 8 (8192 + 6528 \[Lambda] + 1273 \[Lambda]^2 - 12977 \[Lambda]^3 + 5176 \[Lambda]^4)))/131072)
            term1 = (2*(-1 + lam) - lam)
            term2 = (433*(-1 + lam)*(lam**3)
                     + 2*(lam**2)*(3919 - 7780*lam + 3861*(lam**2))
                     - 8*lam*(3264 + 2596*lam - 10595*(lam**2) + 4735*(lam**3))
                     + 8*(8192 + 6528*lam + 1273*(lam**2) - 12977*(lam**3) + 5176*(lam**4)))
            return -(term1 * term2) / 131072
        elif n == 7:
            # 1/33554432(2 (-1 + \[Lambda]) - \[Lambda]) (16611 (-1 + \[Lambda]) \[Lambda]^5 + ...
            term1 = (2*(-1 + lam) - lam)
            term2 = (16611*(-1 + lam)*(lam**5)
                     + 2*(lam**4)*(-110854 + 178735*lam - 67881*(lam**2))
                     + 4*(lam**3)*(140637 - 360967*lam + 398041*(lam**2) - 177711*(lam**3))
                     + 8*(lam**2)*(-371328 - 135399*lam + 2280856*(lam**2) - 2624884*(lam**3) + 850755*(lam**4))
                     + 16*lam*(438272 + 619520*lam - 329225*(lam**2) - 3261323*(lam**3) + 3519049*(lam**4) - 986293*(lam**5))
                     + 32*(-524288 - 438272*lam - 248192*(lam**2) + 323987*(lam**3) + 1452288*(lam**4) - 1454330*(lam**5) + 364519*(lam**6)))
            return (1/33554432) * term1 * term2

    # Fallback for k=2, n=5, r=4 (Previous Hardcoded)
    if k == 2 and n == 5 and r == 4:
        # (131072 - 21504*lambda - 56592*lambda^2 - 124920*lambda^3 + 139479*lambda^4 - 34767*lambda^5) / 131072
        numerator = (131072 
                     - 21504 * lam 
                     - 56592 * lam**2 
                     - 124920 * lam**3 
                     + 139479 * lam**4 
                     - 34767 * lam**5)
        return numerator / 131072
    
    print(f"Warning: No theory formula implemented for k={k}, n={n}, r={r}")
    return None

def main():
    parser = argparse.ArgumentParser(description="Plot Experimental vs Theoretical Fidelity")
    parser.add_argument('--n', type=int, required=True, help="Number of registers (3, 5, 7)")
    parser.add_argument('--k', type=int, default=2, help="Block size k")
    parser.add_argument('--trials', type=int, default=3, help="Number of trials r")
    parser.add_argument('--csv', type=str, help="Path to CSV file (optional, defaults to standard path)")
    
    args = parser.parse_args()
    
    # Construct default CSV path if not provided
    # Standard path: results_hybrid_scaling/k{k}_ntrials{r}/data_n{n}.csv
    # Or just results_hybrid_scaling/data_n{n}.csv if structure is flat?
    # User's previous example: results_hybrid_scaling/k2_ntrials4/data_n5.csv
    
    if args.csv:
        csv_path = args.csv
    else:
        # Try finding it in likely locations
        # 1. Structured
        dir1= f"results_hybrid_scaling/k{args.k}_ntrials{args.trials}"
        path1 = f"{dir1}/data_n{args.n}.csv"
        # 2. Flat (from previous qpa_engine run default)
        path2 = f"results_hybrid_scaling/data_n{args.n}.csv"
        
        if os.path.exists(path1):
            csv_path = path1
        elif os.path.exists(path2):
            csv_path = path2
        else:
            print(f"Error: Could not find data file. Checked:\n  {path1}\n  {path2}")
            return

    print(f"Loading data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Extract columns
    if 'lambda' in df.columns:
        x_exp = df['lambda']
    else:
        x_exp = df.iloc[:, 0]
        
    # Column name might be 'fidelity_n5' or just 'fidelity'
    col_name = f'fidelity_n{args.n}'
    if col_name in df.columns:
        y_exp = df[col_name]
    elif 'fidelity' in df.columns:
        y_exp = df['fidelity']
    else:
        y_exp = df.iloc[:, 1]

    # Generate theoretical curve
    x_theory = np.linspace(x_exp.min(), x_exp.max(), 200)
    y_theory = get_theoretical_fidelity(args.n, args.k, args.trials, x_theory)
    
    if y_theory is None:
        print("Skipping plot due to missing theory.")
        return

    # Create Plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Direct Comparison
    ax1.plot(x_exp, y_exp, 'o', label=f'Sim (n={args.n}, k={args.k}, r={args.trials})', color='blue', markersize=6, alpha=0.7)
    ax1.plot(x_theory, y_theory, '-', label='Theory', color='red', linewidth=2)
    ax1.set_xlabel(r'$\lambda$')
    ax1.set_ylabel('Fidelity')
    ax1.set_title(f'Fidelity vs. $\lambda$ (n={args.n})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Residuals (Theory - Simulation)
    # We need to compute theory at exactly the experimental x points
    y_theory_at_exp = get_theoretical_fidelity(args.n, args.k, args.trials, x_exp)
    residuals = y_theory_at_exp - y_exp
    
    ax2.plot(x_exp, residuals, 's-', color='purple', markersize=6, linewidth=1.5)
    ax2.axhline(0, color='black', linestyle='--', linewidth=1)
    ax2.set_xlabel(r'$\lambda$')
    ax2.set_ylabel(r'Difference ($F_{theory} - F_{sim}$)')
    ax2.set_title('Residuals (Theory - Simulation)')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save
    out_name = f"comparison_n{args.n}_k{args.k}_r{args.trials}"
    plt.savefig(f"{dir1}/{out_name}.pdf")
    plt.savefig(f"{dir1}/{out_name}.png")
    print(f"Plots saved to {out_name}.pdf and .png")

if __name__ == "__main__":
    main()
