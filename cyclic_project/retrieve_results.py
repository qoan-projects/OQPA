import argparse
import os
import json
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from tqdm import tqdm

from execution.backend_handler import IBMRuntimeHandler, FakeBackendHandler, AERHandler
from analysis.result_processor import ResultProcessor

def load_job_history(history_path):
    jobs = []
    if not os.path.exists(history_path):
        return []
    with open(history_path, 'r') as f:
        for line in f:
            try:
                jobs.append(json.loads(line))
            except:
                continue
    return jobs

def main():
    parser = argparse.ArgumentParser(description="Retrieve and Process QPA Results")
    parser.add_argument('--backend', type=str, default='ibm', help="Backend type used for submission")
    parser.add_argument('--device', type=str, default='ibm_brisbane', help="Device name")
    parser.add_argument('--n', type=int, default=5, help="Number of registers")
    parser.add_argument('--k', type=int, default=2, help="Qubits per register")
    parser.add_argument('--trials', type=int, default=3, help="Number of trials")
    parser.add_argument('--job-dir', type=str, default=None, help="Directory with job history (default: data/jobs/<backend>/<device>/n<N>_k<K>_t<Trials>)")
    parser.add_argument('--output', type=str, default='retrieved_results.csv', help="Output CSV file")
    parser.add_argument('--filter-tag', type=str, help="Filter jobs by a specific tag (e.g. 'n5')")
    parser.add_argument('--filter-date', type=str, help="Filter jobs from this date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # 1. Initialize Backend Handler (for retrieval)
    if args.backend == 'ibm':
        handler = IBMRuntimeHandler(backend_name=args.device)
        service = handler._get_service()
    elif args.backend == 'fake':
        # Fake backend usually doesn't support persistent job retrieval by ID across sessions
        # unless we implemented a mock database. Assuming standard Qiskit FakeBackend behavior,
        # we can't really "retrieve" unless the job object is in memory.
        # But if we are simulating this flow, maybe we assume it works or skip.
        print("Note: Retrieval from 'fake' backend relies on local result files saved by JobManager.")
        handler = FakeBackendHandler(args.device)
        service = None # Fake handler doesn't have a service
    elif args.backend == 'aer':
        print("Note: Retrieval from 'aer' backend relies on local result files saved by JobManager.")
        handler = AERHandler()
        service = None
    else:
        print(f"Unknown backend: {args.backend}")
        return

    # 2. Load Job History
    # Ensure job_dir is absolute
    if args.job_dir is None:
         # Walk through subdirectories to find all job_history.jsonl files
         project_root = os.path.dirname(os.path.abspath(__file__))
         param_str = f"n{args.n}_k{args.k}_t{args.trials}"
         base_jobs_dir = os.path.join(project_root, "data", "jobs", args.backend, args.device, param_str)
         
         if not os.path.exists(base_jobs_dir):
             print(f"Directory not found: {base_jobs_dir}")
             return

         all_jobs = []
         print(f"Searching for job history in {base_jobs_dir}...")
         
         # Recursively find all job_history.jsonl files
         for root, dirs, files in os.walk(base_jobs_dir):
             if "job_history.jsonl" in files:
                 history_path = os.path.join(root, "job_history.jsonl")
                 
                 jobs = load_job_history(history_path)
                 
                 # New Logic: Check if jobs have 'subdir' field
                 # If yes, we can directly map source_dir.
                 # If no, we fallback to the scan.
                 
                 jobs_missing_path = [j for j in jobs if 'subdir' not in j]
                 
                 job_dir_map = {}
                 if jobs_missing_path:
                     # Fallback Scan (Legacy)
                     # Let's do a quick walk of subdirs to map job_id -> directory
                     for sub_root, _, sub_files in os.walk(root):
                          for f in sub_files:
                              if f.endswith("_result.json") or f.endswith("_circuit_meta.json"):
                                  # format: {job_id}_result.json
                                  jid = f.split('_')[0]
                                  job_dir_map[jid] = sub_root
                 
                 for job in jobs:
                     if 'subdir' in job:
                         # Use the explicit relative path
                         # The subdir is relative to the history_path's directory (usually pXX)
                         job['_source_dir'] = os.path.join(root, job['subdir'])
                     else:
                         # Fallback
                         jid = job['job_id']
                         if jid in job_dir_map:
                             job['_source_dir'] = job_dir_map[jid]
                         else:
                             # Fallback: maybe it's in the same dir
                             job['_source_dir'] = root
                 
                 all_jobs.extend(jobs)
                 
         print(f"Loaded {len(all_jobs)} jobs from history across subdirectories.")

    else:
        if not os.path.isabs(args.job_dir):
             args.job_dir = os.path.abspath(args.job_dir)
             
        history_file = os.path.join(args.job_dir, "job_history.jsonl")
        all_jobs = load_job_history(history_file)
        # Add source dir
        for job in all_jobs:
            job['_source_dir'] = args.job_dir
            
        print(f"Loaded {len(all_jobs)} jobs from history.")
    
    # 3. Filter Jobs
    filtered_jobs = []
    for job in all_jobs:
        # Check date
        if args.filter_date and not job['timestamp'].startswith(args.filter_date):
            continue
        # Check tag
        if args.filter_tag and args.filter_tag not in job['tags']:
            continue
            
        filtered_jobs.append(job)
        
    print(f"Found {len(filtered_jobs)} jobs matching filters.")
    if not filtered_jobs:
        return

    # 4. Group by Experiment (Epsilon)
    # We group by epsilon to aggregate batches
    experiments = defaultdict(list)
    for job in filtered_jobs:
        eps = job['metadata'].get('epsilon')
        if eps is not None:
            experiments[eps].append(job)
            
    # 5. Process Each Experiment
    results_data = []
    
    # Sort lambdas
    sorted_lambdas = sorted(experiments.keys())
    
    print("\n--- Processing Experiments ---")
    for epsilon in tqdm(sorted_lambdas):
        job_list = experiments[epsilon]
        
        # We need to reconstruct the total aggregation
        # Main.py logic: aggregated_fidelity_sum += batch_fid
        # Final = sum / total_instances
        
        aggregated_fidelity_sum = 0.0
        total_circuits_accumulated = 0
        k_val = 2 # Default
        
        # New Accumulator for Global Stats over all batches
        # Key: cond_key (path type), Value: {'success': 0, 'total': 0}
        global_path_stats = defaultdict(lambda: {'success': 0, 'total': 0})
        
        # Check metadata from first job to get constants and determine paths
        num_paths_per_instance = 1 # Default for dynamic
        
        if job_list:
            first_meta = job_list[0]['metadata']
            k_val = first_meta.get('k', 2)
            
            # Determine paths per instance for unrolled
            # Load the circuit metadata from the first job
            first_job_id = job_list[0]['job_id']
            # Use source dir from the job record
            source_dir = job_list[0].get('_source_dir', args.job_dir)
            
            meta_path = os.path.join(source_dir, f"{first_job_id}_circuit_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    batch_meta_sample = json.load(f)
                    
                # Count unique condition sets to determine paths
                unique_conditions = set()              
                for item in batch_meta_sample:
                    # Conditions are dict {str_idx: val}, convert to tuple for set
                    # Keys are strings in JSON, need to sort to ensure consistency
                    if 'conditions' in item:
                        conds = tuple(sorted((int(k), v) for k, v in item['conditions'].items()))
                    else:
                        conds = () # Empty tuple for no conditions
                    unique_conditions.add(conds)
                
                if unique_conditions:
                    num_paths_per_instance = len(unique_conditions)
                    print(f"DEBUG: First job {first_job_id} has {len(batch_meta_sample)} metadata entries.")
                    print(f"DEBUG: Detected {num_paths_per_instance} unique condition sets (paths per instance).")
                    print(f"DEBUG: Unique Conditions: {unique_conditions}")
                    
                    # Validation: Total entries should be multiple of paths
                    if len(batch_meta_sample) % num_paths_per_instance != 0:
                         print(f"WARNING: Batch metadata length {len(batch_meta_sample)} is not divisible by num_paths {num_paths_per_instance}!")
        
        # Override if dynamic (should be 1)
        processor = ResultProcessor(k_val)
        
        successful_batches = 0
        
        for job_record in job_list:
            job_id = job_record['job_id']
            source_dir = job_record.get('_source_dir', args.job_dir)
            
            # Load Circuit Metadata (Conditions)
            meta_path = os.path.join(source_dir, f"{job_id}_circuit_meta.json")
            if not os.path.exists(meta_path):
                print(f"Missing circuit metadata for job {job_id}, skipping.")
                continue
                
            with open(meta_path, 'r') as f:
                batch_metadata = json.load(f)
                
            # Fix JSON integer keys (they become strings after reload)
            for item in batch_metadata:
                if 'conditions' in item:
                    item['conditions'] = {int(k): v for k, v in item['conditions'].items()}
                
            # Retrieve Job Result
            try:
                extracted_counts = []
                
                if args.backend == 'ibm':
                    qiskit_job = service.job(job_id)
                    pub_result = qiskit_job.result()
                    
                    # Use ResultProcessor to extract counts
                    method = job_record['metadata'].get('method', 'unrolled')
                    is_dynamic = (method == 'dynamic')
                    extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                    
                elif args.backend in ['fake', 'aer']:
                    # Load from local result JSON
                    result_path = os.path.join(source_dir, f"{job_id}_result.json")
                    if not os.path.exists(result_path):
                        print(f"Result file not found for {args.backend} job {job_id}, skipping.")
                        continue
                        
                    with open(result_path, 'r') as f:
                        extracted_counts = json.load(f)
                
                else:
                    continue

                # Prepare total_clbits_list for processing
                # Estimate total bits from the first key in each count dictionary
                total_clbits_list = []
                for counts in extracted_counts:
                    if counts:
                        first_key = next(iter(counts))
                        total_clbits_list.append(len(first_key.replace(" ", "")))
                    else:
                        total_clbits_list.append(0)

                # Calculate Batch Stats and Accumulate
                batch_stats = processor.aggregate_batch_stats(extracted_counts, batch_metadata, total_clbits_list)
                
                for cond_key, stats in batch_stats.items():
                    global_path_stats[cond_key]['success'] += stats['success']
                    global_path_stats[cond_key]['total'] += stats['total']
                
                successful_batches += 1
                
                # DEBUG: Check first batch
                if successful_batches == 1:
                     # Compute provisional fidelity for debug
                     temp_fid = 0.0
                     print(f"DEBUG: Batch 1 - Circuits: {len(extracted_counts)}")
                     for cond_key, stats in batch_stats.items():
                         path_prob = stats['success'] / stats['total'] if stats['total'] > 0 else 0
                         temp_fid += path_prob
                         print(f"DEBUG: Path {cond_key} -> Success: {stats['success']}, Total: {stats['total']}, Prob: {path_prob:.4f}")
                     print(f"DEBUG: Batch 1 - Batch Fid: {temp_fid:.4f}")
                
            except Exception as e:
                print(f"Failed to retrieve/process job {job_id}: {e}")
                
        # Final Calculation over accumulated global stats
        final_fid = 0.0
        variance_sum = 0.0
        
        if global_path_stats:
            print(f"DEBUG: Global Stats for Lambda={epsilon:.4f}")
            for cond_key, stats in global_path_stats.items():
                if stats['total'] > 0:
                    path_prob = stats['success'] / stats['total']
                    final_fid += path_prob
                    
                    # Variance of this path's contribution: Var(N_succ / N_tot) = Var(N_succ) / N_tot^2
                    # Assuming Bernoulli statistics: Var(N_succ) = N_tot * p * (1-p) = N_succ * (1 - N_succ/N_tot)
                    # Var(N_succ) = N_succ * (N_tot - N_succ) / N_tot
                    # So Var_path = (N_succ * (N_tot - N_succ) / N_tot) / N_tot^2 = N_succ * (N_tot - N_succ) / N_tot^3
                    variance_sum += (stats['success'] * (stats['total'] - stats['success'])) / (stats['total'] ** 3)
                    
                print(f"DEBUG: GLOBAL Path {cond_key} -> Success: {stats['success']}, Total: {stats['total']}, Prob: {path_prob:.4f}")
        
        error_est = np.sqrt(variance_sum)
        
        print(f"Lambda={epsilon:.4f} -> Fidelity={final_fid:.4f} +/- {error_est:.4f} (Batches: {successful_batches}/{len(job_list)})")
        results_data.append({'lambda': epsilon, 'fidelity': final_fid, 'error': error_est})

    # Save
    df = pd.DataFrame(results_data)
    df.to_csv(args.output, index=False)
    print(f"Saved retrieved results to {args.output}")

if __name__ == "__main__":
    main()
