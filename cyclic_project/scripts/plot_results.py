import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import argparse
import re
import itertools

# --- Configuration ---
# Add your CSV files here if you prefer not to use CLI arguments.
FILES_TO_PLOT = [
    # "../data/results/k2/n5/n_trials3/results_aer_dynamic.csv",
    "../data/results/k2/n5/n_trials3/results_ibm.csv",
    "../data/results/k2/n3/n_trials3/results_ibm.csv",
    "../data/results/k2/n5/n_trials3/results_fake.csv",
    "../data/results/k2/n3/n_trials3/results_fake.csv",
]

OUTPUT_FILE = "../data/plots/k2/multiple_n/n_trials3/fidelity_plot_withfake.png"

# Style settings
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 12,
    'axes.labelsize': 14,
    'axes.titlesize': 16,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 11,
    'lines.linewidth': 2,
    'lines.markersize': 8
})

# --- Theoretical Curves ---
def theory_curve(lam, n, k):
    """
    Returns the theoretical fidelity for a given lambda, n, and k.
    d = 2^k
    """
    if k == 1: # d=2
        if n == 3:
            return (1/6) * (6 - lam - 3*lam**2 + lam**3)
        elif n == 5:
            return (1/120) * (120 - 12*lam - 28*lam**2 - 64*lam**3 + 55*lam**4 - 11*lam**5)
        elif n == 7:
            return (1/1680) * (1680 - 120*lam - 264*lam**2 - 464*lam**3 - 1000*lam**4 + 1614*lam**5 - 707*lam**6 + 101*lam**7)
    elif k == 2: # d=4
        if n == 3:
            return (1/8) * (8 - 2*lam - 7*lam**2 + 3*lam**3)
        elif n == 5:
            return (1/640) * (640 - 96*lam - 224*lam**2 - 700*lam**3 + 693*lam**4 - 153*lam**5)
        elif n == 7:
            return (1/215040) * (215040 - 23040*lam - 50688*lam**2 - 88768*lam**3 - 311056*lam**4 + 497192*lam**5 - 207951*lam**6 + 23031*lam**7)
    
    return None

def get_params_from_path(filepath):
    """Extract n, k, trials from filepath using regex."""
    path_params = re.search(r'n(\d+)_k(\d+)_t(\d+)', filepath)
    if path_params:
        return tuple(map(int, path_params.groups()))
    
    # Fallback checks
    n = 5 # Default
    if "n3" in filepath: n = 3
    elif "n5" in filepath: n = 5
    elif "n7" in filepath: n = 7
    
    k = 2 # Default
    if "k1" in filepath: k = 1
    elif "k2" in filepath: k = 2
    
    return n, k, 3 # Assume t=3 if not found

def get_backend_from_path(filepath):
    """Identify backend from filepath."""
    filepath_lower = filepath.lower()
    if "ibm" in filepath_lower:
        return "IBM"
    elif "fake" in filepath_lower:
        return "Fake"
    elif "aer" in filepath_lower:
        return "Aer"
    return "Unknown"

def main():
    parser = argparse.ArgumentParser(description="Plot QPA Fidelity Results")
    parser.add_argument('files', metavar='F', type=str, nargs='*', help='CSV files to plot (overrides config)')
    parser.add_argument('--output', type=str, default=None, help='Output image file path (overrides config)')
    parser.add_argument('--title', type=str, default='QPA Fidelity Decay', help='Plot title')
    
    # Theory arguments
    parser.add_argument('--theory-n', type=int, help='N value for first theoretical curve')
    parser.add_argument('--theory-k', type=int, help='K value for first theoretical curve')
    parser.add_argument('--theory-n2', type=int, help='N value for second theoretical curve')
    parser.add_argument('--theory-k2', type=int, help='K value for second theoretical curve')
    
    args = parser.parse_args()

    files_to_plot = args.files if args.files else FILES_TO_PLOT
    output_path = args.output if args.output else OUTPUT_FILE

    if not files_to_plot:
        print("No files provided via CLI or configuration.")
        return

    # 1. Collect Data and Metadata
    data_entries = []
    unique_params = set() # (n, k)
    unique_backends = set()
    
    for filepath in files_to_plot:
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            continue

        try:
            print(f"Reading {filepath}...")
            df = pd.read_csv(filepath)
            
            if 'lambda' not in df.columns or 'fidelity' not in df.columns:
                print(f"Skipping {filepath}: Columns 'lambda' and 'fidelity' not found.")
                continue
                
            n, k, t = get_params_from_path(filepath)
            backend = get_backend_from_path(filepath)
            
            unique_params.add((n, k))
            unique_backends.add(backend)
            
            data_entries.append({
                'df': df,
                'n': n,
                'k': k,
                't': t,
                'backend': backend,
                'path': filepath
            })
            
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    if not data_entries:
        print("No valid data found to plot.")
        return

    # 2. Assign Colors and Markers
    # Color map for (n, k) tuples
    # Use a high contrast colormap
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_params)))
    param_color_map = {param: colors[i] for i, param in enumerate(sorted(list(unique_params)))}
    
    # Marker map for backends
    markers = ['o', 's', '^', 'D', 'v', '<', '>']
    backend_marker_map = {backend: markers[i % len(markers)] for i, backend in enumerate(sorted(list(unique_backends)))}
    
    # Linestyle map for backends (optional, maybe keep solid for all but change transparency or dash)
    # Let's keep solid for data, dashed for theory
    backend_linestyle_map = {
        "IBM": "-",
        "Fake": "-.",
        "Aer": ":",
        "Unknown": "-"
    }
    
    plt.figure(figsize=(12, 8))

    # 3. Plot Data
    for entry in data_entries:
        df = entry['df']
        n, k, t = entry['n'], entry['k'], entry['t']
        backend = entry['backend']
        
        color = param_color_map[(n, k)]
        marker = backend_marker_map[backend]
        linestyle = backend_linestyle_map.get(backend, "-")
        
        label = f"{backend} (N={n}, K={k}, T={t})"
        
        # Check for error column
        if 'error' in df.columns:
            plt.errorbar(
                df['lambda'], 
                df['fidelity'], 
                yerr=df['error'], 
                marker=marker, 
                color=color, 
                linestyle=linestyle, 
                linewidth=2,
                capsize=5, 
                label=label,
                alpha=0.8
            )
        else:
            plt.plot(
                df['lambda'], 
                df['fidelity'], 
                marker=marker, 
                color=color, 
                linestyle=linestyle, 
                linewidth=2,
                label=label,
                alpha=0.8
            )

    # 4. Plot Theory Curves
    # If explicit theory args provided
    theory_params = []
    if args.theory_n and args.theory_k:
        theory_params.append((args.theory_n, args.theory_k))
    if args.theory_n2 and args.theory_k2:
        theory_params.append((args.theory_n2, args.theory_k2))
        
    # Also automatically add theory curves for plotted data if not redundant
    for (n, k) in unique_params:
        if (n, k) not in theory_params:
            theory_params.append((n, k))
            
    lam_values = np.linspace(0, 1, 100)
    
    for (n, k) in theory_params:
        fid_values = theory_curve(lam_values, n, k)
        if fid_values is not None:
            # Use same color as data if it exists in map, else black
            color = param_color_map.get((n, k), 'black')
            
            label = f"Theory (N={n}, K={k})"
            plt.plot(lam_values, fid_values, color=color, linestyle='--', linewidth=1.5, label=label, alpha=0.6)
            
            # Plot baseline limit
            random_limit = 1.0 / (2**k)
            # plt.axhline(y=random_limit, color=color, linestyle=':', alpha=0.3)
            
    # 5. Finalize Plot
    plt.title(args.title, fontweight='bold')
    plt.xlabel(r"Depolarizing Noise Strength ($\lambda$)")
    plt.ylabel("Purified Fidelity")
    plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
    plt.legend(loc='best', frameon=True, shadow=True)
    plt.ylim(-0.05, 1.05)
    plt.xlim(-0.05, 1.05)
    
    # Ensure directory exists for output
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    print(f"\nPlot saved to {output_path}")

if __name__ == "__main__":
    main()
