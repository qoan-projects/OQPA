import os
import glob
import pandas as pd
import argparse
import shutil
import re
from collections import defaultdict

def parse_filename(filepath):
    filename = os.path.basename(filepath)
    # Match: result_eps0p001_steps4.csv
    match = re.search(r"result_eps([\d\w]+)_steps(\d+)\.csv", filename)
    if match:
        eps_str = match.group(1).replace('p', '.')
        steps_str = match.group(2)
        return float(eps_str), int(steps_str)
    return None, None

def parse_shots_from_folder(folder_path):
    foldername = os.path.basename(folder_path)
    if foldername.startswith("shots"):
        try:
            return int(foldername.replace("shots", ""))
        except ValueError:
            return 0
    return 0

def merge_csvs_and_save(csv_files, shot_count, output_path):
    """
    Reads multiple CSVs (same eps, same steps) and averages their fidelity.
    """
    fidelities = []
    eps_val, steps_val = None, None
    
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if not df.empty and 'fidelity' in df.columns:
                fidelities.append(df['fidelity'].iloc[0])
                if eps_val is None:
                    eps_val, steps_val = parse_filename(f)
        except: pass
        
    if not fidelities: return
    
    # Average fidelity
    avg_fid = sum(fidelities) / len(fidelities)
    
    # Create new DataFrame with standardized columns
    new_df = pd.DataFrame({
        'epsilon': [eps_val],
        'steps': [steps_val],
        'fidelity': [avg_fid],
        'shots': [shot_count * len(fidelities)]
    })
    
    new_df.to_csv(output_path, index=False)

def reorganize_data(src_base, dest_base, t, J, h, k):
    """
    Consolidates multiple result_epsX_stepsY.csv files into a single merged CSV per shot folder.
    """
    
    params_path = f"t{str(t).replace('.','p')}_J{str(J).replace('.','p')}_h{str(h).replace('.','p')}"
    k_path = f"k{k}"
    root_src = os.path.join(src_base, params_path, k_path)
    
    if not os.path.exists(root_src):
        print(f"Source directory not found: {root_src}")
        return

    print(f"Scanning {root_src}...")
    
    for subdir in os.listdir(root_src):
        src_n_path = os.path.join(root_src, subdir)
        if not os.path.isdir(src_n_path): continue
        
        # Determine n
        if subdir == "unamplified":
            trials_dirs = [(".", src_n_path)]
        else:
            trials_dirs = [(d, os.path.join(src_n_path, d)) for d in os.listdir(src_n_path) if d.startswith("trials")]
            
        for t_name, t_path in trials_dirs:
            if not os.path.isdir(t_path): continue
            
            shots_dirs = [d for d in os.listdir(t_path) if d.startswith("shots")]
            
            for s_name in shots_dirs:
                s_path = os.path.join(t_path, s_name)
                if not os.path.isdir(s_path): continue
                
                shot_count = parse_shots_from_folder(s_path)
                
                # Create destination path
                if subdir == "unamplified":
                    dest_dir = os.path.join(dest_base, params_path, k_path, "unamplified", s_name)
                else:
                    dest_dir = os.path.join(dest_base, params_path, k_path, subdir, t_name, s_name)
                
                os.makedirs(dest_dir, exist_ok=True)
                
                # Find all CSVs in this shot folder
                csv_files = glob.glob(os.path.join(s_path, "*.csv"))
                
                # Parse them all into a list of dictionaries
                rows = []
                for csv_f in csv_files:
                    eps, steps = parse_filename(csv_f)
                    if eps is None or steps is None: continue
                    
                    try:
                        df = pd.read_csv(csv_f)
                        if not df.empty and 'fidelity' in df.columns:
                            fid = df['fidelity'].iloc[0]
                            rows.append({
                                'epsilon': eps,
                                'steps': steps,
                                'fidelity': fid,
                                'shots': shot_count # Individual shots per file
                            })
                    except: pass
                
                if not rows: continue
                
                # Create a single merged DataFrame
                full_df = pd.DataFrame(rows)
                
                # If there are duplicates for (epsilon, steps), merge them (average fidelity, sum shots?)
                # We usually average fidelity, and sum shots if we treat them as independent runs.
                # Or just list them? 
                # User asked: "save a CSV containing at (eps,steps,fidelity) values"
                # "It is quite literally jus merging them all in a single file"
                # So we want ONE file with many rows.
                
                # Let's aggregate by (epsilon, steps) just in case
                # Aggregation: average fidelity, sum shots (or keep original shots? Plot script expects total shots?)
                # Plot script does: aggregated...['w_sum'] += fid * shot_count
                # So if we provide rows with (fidelity, shots), it works.
                
                # But let's keep rows distinct or aggregate? 
                # If we aggregate, file is smaller.
                # GroupBy (epsilon, steps)
                # fidelity -> mean
                # shots -> sum (actually plot script assumes 'shot_count' is per entry)
                # If we average fidelity, the effective shots is sum(shots).
                
                agg_df = full_df.groupby(['epsilon', 'steps']).agg({
                    'fidelity': 'mean',
                    'shots': 'sum' # If we merged 2 runs of 20000 shots, we have 40000 shots worth of data
                }).reset_index()
                
                # Sort for tidiness
                agg_df.sort_values(['epsilon', 'steps'], inplace=True)
                
                # Save as ONE merged file
                merged_filename = "results_merged.csv"
                agg_df.to_csv(os.path.join(dest_dir, merged_filename), index=False)

    print(f"Reorganization complete. Data saved to {dest_base}")

def main():
    parser = argparse.ArgumentParser(description="Reorganize Aer Trotter Data")
    parser.add_argument('--src', type=str, default='aer_trotter_data/results')
    parser.add_argument('--dest', type=str, default='simplified_aer_trotter_data/results')
    
    t, J, h, k = 1.0, 1.0, 1.0, 2
    args = parser.parse_args()
    
    reorganize_data(args.src, args.dest, t, J, h, k)

if __name__ == "__main__":
    main()
