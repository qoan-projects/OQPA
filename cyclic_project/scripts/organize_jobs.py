import os
import re
import shutil
from datetime import datetime
import glob

# Configuration
LOG_FILE = "../data/logs/qpa_8894027.out"
BASE_JOBS_DIR = "../data/jobs/ibm/ibm_boston"

def parse_log_file(log_path):
    with open(log_path, 'r') as f:
        content = f.read()

    # Extract Parameters
    n_match = re.search(r"Topology: N=(\d+)", content)
    k_match = re.search(r"K=(\d+)", content)
    t_match = re.search(r"Trials=(\d+)", content)
    
    p_match = re.search(r"Noise: .* \((\d+) points\)", content)
    c_match = re.search(r"Twirling: (\d+) instances", content)
    
    # Shots is a bit trickier, usually in "Splitting X total shots"
    s_match = re.search(r"Splitting (\d+) total shots", content)
    
    # Date
    # Example: Date: Fri Feb  6 23:15:07 EST 2026
    date_match = re.search(r"Date: \w+ (\w+)\s+(\d+) (\d{2}:\d{2}:\d{2}) \w+ (\d{4})", content)
    
    if not (n_match and k_match and t_match and p_match and c_match and s_match and date_match):
        print("Error: Could not parse all parameters from log.")
        return None

    n = n_match.group(1)
    k = k_match.group(1)
    t = t_match.group(1)
    points = p_match.group(1)
    n_random = c_match.group(1)
    shots = s_match.group(1)
    
    # Parse Date to YYYYMMDD_HHMMSS
    month_str, day, time, year = date_match.groups()
    dt_str = f"{month_str} {day} {time} {year}"
    dt_obj = datetime.strptime(dt_str, "%b %d %H:%M:%S %Y")
    timestamp = dt_obj.strftime("%Y%m%d_%H%M%S")
    
    # Extract Job IDs
    job_ids = re.findall(r"Job submitted(?: \(Post-Only\))?! ID: ([a-z0-9]+)", content)
    # Unique IDs
    job_ids = list(set(job_ids))
    
    return {
        'n': n, 'k': k, 't': t,
        'p': points, 's': shots, 'c': n_random,
        'timestamp': timestamp,
        'job_ids': job_ids
    }

def main():
    # Use global to modify global variables
    global LOG_FILE, BASE_JOBS_DIR
    
    if not os.path.exists(LOG_FILE):
        # Fallback to absolute path if relative fails (depending on where script is run)
        abs_log = os.path.abspath(LOG_FILE)
        if not os.path.exists(abs_log):
             # Try assuming script is run from project root, not scripts/
             alt_log = LOG_FILE.replace("../", "")
             if os.path.exists(alt_log):
                 LOG_FILE = alt_log
                 BASE_JOBS_DIR = "data/jobs/ibm/ibm_boston"
             else:
                 print(f"Log file not found: {LOG_FILE} or {abs_log}")
                 return
        else:
            LOG_FILE = abs_log

    print(f"Parsing {LOG_FILE}...")
    params = parse_log_file(LOG_FILE)
    if not params:
        return
        
    print(f"Found {len(params['job_ids'])} Job IDs.")
    print(f"Parameters: {params}")
    
    # Construct Paths
    # Source: n3_k2_t3 (as per user instruction, the files are currently here)
    src_subdir = f"n{params['n']}_k{params['k']}_t{params['t']}"
    src_dir = os.path.join(BASE_JOBS_DIR, src_subdir)
    
    # Target: n3_k2_t3/p25/s4000_c800/20260206_231507
    p_str = f"p{params['p']}"
    config_str = f"s{params['s']}_c{params['c']}"
    dest_dir = os.path.join(src_dir, p_str, config_str, params['timestamp'])
    
    print(f"Source Dir: {src_dir}")
    print(f"Target Dir: {dest_dir}")
    
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print("Created target directory.")
        
    # --- UPDATE JOB HISTORY ---
    # Update job_history.jsonl in p25/job_history.jsonl
    history_file = os.path.join(src_dir, p_str, "job_history.jsonl")
    
    if os.path.exists(history_file):
        print(f"Updating job history in {history_file}...")
        updated_lines = []
        import json
        
        # Determine relative path from pXX to dest_dir
        # dest_dir is .../pXX/sXX_cXX/timestamp
        # history_file is .../pXX/job_history.jsonl
        # rel_path should be sXX_cXX/timestamp
        rel_path = os.path.relpath(dest_dir, os.path.dirname(history_file))
        
        with open(history_file, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record['job_id'] in params['job_ids']:
                        record['subdir'] = rel_path
                    updated_lines.append(json.dumps(record))
                except:
                    updated_lines.append(line.strip())
        
        with open(history_file, 'w') as f:
            for line in updated_lines:
                f.write(line + "\n")
        print("Job history updated with subdir paths.")
    else:
        print(f"Warning: Job history file not found at {history_file}")

    # Move Files
    count = 0
    for job_id in params['job_ids']:
        # Look for files with this job_id in filename in src_dir
        # e.g. {job_id}_circuit_meta.json
        pattern = os.path.join(src_dir, f"*{job_id}*.json")
        files = glob.glob(pattern)
        
        for fpath in files:
            fname = os.path.basename(fpath)
            dest_path = os.path.join(dest_dir, fname)
            
            try:
                shutil.move(fpath, dest_path)
                # print(f"Moved {fname}")
                count += 1
            except Exception as e:
                print(f"Error moving {fname}: {e}")
                
    print(f"Successfully moved {count} files to {dest_dir}")

if __name__ == "__main__":
    main()
