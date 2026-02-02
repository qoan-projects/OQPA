import pandas as pd
import matplotlib.pyplot as plt
import os

# --- Configuration ---
# Add your CSV files here. 
# Paths should be relative to where you run this script (assumed to be from scripts/ folder)
# or absolute paths.
FILES_TO_PLOT = [
    "../data/results/k2/n5/n_trials3/results_aer_dynamic.csv",
    "../data/results/k2/n5/n_trials3/results_fake.csv",
    "../data/results/k2/n5/n_trials3/results_ibm.csv",
    # "../data/results/k2/n5/n_trials3/data_n5.csv"
    # "../data/results/results_fake.csv" 
]

OUTPUT_DIR = "../data/plots/k2/n5/n_trials3/"
# ---------------------

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    plt.figure(figsize=(10, 6))

    has_data = False
    for filepath in FILES_TO_PLOT:
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            continue

        try:
            print(f"Plotting {filepath}...")
            df = pd.read_csv(filepath)
            
            # Extract label from filename for the legend
            label = os.path.basename(filepath).replace("results_", "").replace(".csv", "")
            
            # Plot
            # Assuming columns are 'lambda' and 'fidelity' based on main.py output
            if 'lambda' in df.columns and 'fidelity' in df.columns:
                plt.plot(df['lambda'], df['fidelity'], marker='o', linestyle='-', label=label)
                has_data = True
            else:
                print(f"Skipping {filepath}: Columns 'lambda' and 'fidelity' not found.")
                
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    if has_data:
        plt.title("QPA Fidelity Decay")
        plt.xlabel("Lambda (Noise Parameter)")
        plt.ylabel("Purified Fidelity")
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.legend()
        
        output_path = os.path.join(OUTPUT_DIR, "fidelity_plot.png")
        plt.savefig(output_path, dpi=300)
        print(f"\nPlot saved to {output_path}")
    else:
        print("\nNo valid data found to plot.")

if __name__ == "__main__":
    main()
