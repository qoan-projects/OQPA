import argparse
import pandas as pd
import glob
import os

def main():
    parser = argparse.ArgumentParser(description="Merge partial QPA result CSVs")
    parser.add_argument('--pattern', type=str, default="results_task*.csv", help="Glob pattern for partial results")
    parser.add_argument('--output', type=str, default="results_merged.csv", help="Output merged CSV file")
    
    args = parser.parse_args()
    
    files = glob.glob(args.pattern)
    if not files:
        print(f"No files found matching pattern: {args.pattern}")
        return

    print(f"Found {len(files)} partial result files.")
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if dfs:
        merged_df = pd.concat(dfs, ignore_index=True)
        
        # Sort by lambda if present
        if 'lambda' in merged_df.columns:
            merged_df = merged_df.sort_values(by='lambda')
            
        merged_df.to_csv(args.output, index=False)
        print(f"Merged results saved to {args.output}")
        print(merged_df)
    else:
        print("No valid data found to merge.")

if __name__ == "__main__":
    main()
