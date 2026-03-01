import pandas as pd
import glob
import os
import re
import argparse

def main():
    parser = argparse.ArgumentParser(description="Combine individual fidelity result files into a single CSV.")
    parser.add_argument('--outdir', type=str, required=True, help='Directory containing fidelity result files.')
    args = parser.parse_args()

    outdir = args.outdir

    # Match both epsilon and lambda files
    pattern = os.path.join(outdir, "fidelity_*_eps*.csv")
    files = glob.glob(pattern)
    if not files:
        pattern = os.path.join(outdir, "fidelity_*_lam*.csv")
        files = glob.glob(pattern)
    if not files:
        raise RuntimeError("No matching files found for either epsilon or lambda.")

    # Determine whether it's epsilon or lambda from first file
    basename = os.path.basename(files[0])
    match = re.search(r'(epsilon|lambda)([\d.]+)-([\d.]+)_steps(\d+)', basename)
    if not match:
        raise RuntimeError("Filename format not recognized.")

    noise_type, min_val, max_val, steps = match.groups()

    # Sort files numerically by eps or lam index
    def extract_index(f):
        tag = "eps" if "eps" in f else "lam"
        match = re.search(rf'{tag}(\d+)', f)
        return int(match.group(1)) if match else -1

    files = sorted(files, key=extract_index)

    # Read and combine files
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        if len(df) != 1:
            raise ValueError(f"Expected 1 row in {f}, but got {len(df)}.")
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)

    # Build output filename
    combined_name = f"fidelity_combined_{noise_type}{min_val}-{max_val}_steps{steps}.csv"
    combined_path = os.path.join(outdir, combined_name)
    combined.to_csv(combined_path, index=False)

    print(f"[+] Combined {len(files)} files into:\n    {combined_path}")

if __name__ == '__main__':
    main()
