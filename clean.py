import pandas as pd
import glob
import os

# Define path to your results (update if needed)
outdir = "data/d5_shots102400_nqpa2"
pattern = os.path.join(outdir, "fidelity_lambda0.0-1.0_steps40_lam*.csv")

# Get all matching files and sort by lambda index
files = sorted(glob.glob(pattern), key=lambda x: int(x.split("lam")[-1].split(".csv")[0]))

# Read each file and combine into one DataFrame
dfs = [pd.read_csv(f) for f in files]
combined = pd.concat(dfs, ignore_index=True)

# Save to combined output
combined_path = os.path.join(outdir, "fidelity_combined.csv")
combined.to_csv(combined_path, index=False)

print(f"[+] Combined 102400-shot results saved to:\n    {combined_path}")
