import os
import pandas as pd
from pathlib import Path
import argparse
from tqdm import tqdm

def combine_lambda_files(base_folder: Path, dry_run: bool = False):
    """Combine all lambda CSV files in each nqpa folder into a single file."""
    # Get all nqpa directories
    nqpa_dirs = [d for d in base_folder.iterdir() if d.is_dir()]
    
    for nqpa_dir in tqdm(nqpa_dirs, desc="Processing nqpa folders"):
        # Get all CSV files in this nqpa directory
        csv_files = sorted(nqpa_dir.glob("*.csv"))
        if not csv_files:
            continue

        # Read and concatenate all CSV files
        dfs = []
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            dfs.append(df)
        
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Save the combined file
        output_path = nqpa_dir / "combined_lambda.csv"

        combined_df.to_csv(output_path, index=False)
        print(f"[+] Combined {len(csv_files)} files into {output_path}")
        
        # Optionally remove the original files
        if not dry_run:
            for csv_file in csv_files:
                if csv_file != output_path:
                    csv_file.unlink()
                    print(f"[-] Removed {csv_file}")

def main():
    base_folder_name = 'data/ibm_global_sampler/simulation_outputs/ibm_global_sampler_k2_shots3000_lambda0.0-1.0_s20_r3000_g0_aerfalse_faketrue'
    base_folder = Path(base_folder_name).resolve()
    if not base_folder.exists():
        raise ValueError(f"Base folder {base_folder} does not exist")
    
    combine_lambda_files(base_folder, dry_run=True)

if __name__ == "__main__":
    main()
