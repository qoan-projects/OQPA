import pandas as pd
import glob
import os
import re
import argparse
import shutil

def combine_job_folder(path, dest_dir):
    base = os.path.basename(path)
    files = sorted(
        glob.glob(os.path.join(path, "nqpa*_ntrot*_eps*.csv")),
        key=lambda f: int(re.search(r'eps(\d+)', f).group(1))
    )

    if not files:
        print(f"[!] Skipping {base}: no matching eps files.")
        return

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        if len(df) != 1:
            print(f"[!] Warning: {f} has {len(df)} rows, expected 1.")
            continue
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    combined_filename = f"{base}_combined.csv"
    combined_path = os.path.join(path, combined_filename)
    combined.to_csv(combined_path, index=False)

    # Move to shared_data
    dest_path = os.path.join(dest_dir, combined_filename)
    shutil.move(combined_path, dest_path)
    print(f"[+] Moved {combined_filename} → {dest_path}")

def main():
    parser = argparse.ArgumentParser(description="Combine fidelity files and move outputs to shared_data.")
    parser.add_argument('--parentdir', type=str, required=True,
                        help='Parent directory containing job subfolders.')
    parser.add_argument('--dest', type=str, default='shared_data',
                        help='Base destination folder to store combined results.')
    args = parser.parse_args()

    # Recreate substructure under dest
    tag = os.path.basename(os.path.normpath(args.parentdir))
    full_dest = os.path.join(args.dest, tag)
    os.makedirs(full_dest, exist_ok=True)

    for entry in sorted(os.listdir(args.parentdir)):
        subdir = os.path.join(args.parentdir, entry)
        if os.path.isdir(subdir) and re.match(r'\d+_nqpa\d+_ntrot\d+', entry):
            combine_job_folder(subdir, full_dest)

if __name__ == '__main__':
    main()


#example: python combine_dataa.py --parentdir data/estimation_k3_shots102400_eps0.0-0.009_s40