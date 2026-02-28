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
    parser.add_argument('--no-reset', action='store_true', help="Retrieve jobs from the 'no_reset' subfolder")
    
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
         
         if args.no_reset:
             base_jobs_dir = os.path.join(project_root, "data", "jobs", args.backend, args.device, "no_reset", param_str)
         else:
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
            if 'subdir' in job:
                job['_source_dir'] = os.path.join(args.job_dir, job['subdir'])
            else:
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
        meta = job.get('metadata', {})
        eps = meta.get('epsilon')
        
        # If not found, check pubs_metadata (Parameterized style)
        if eps is None and 'pubs_metadata' in meta:
            pubs_meta = meta['pubs_metadata']
            if isinstance(pubs_meta, list) and len(pubs_meta) > 0:
                eps = pubs_meta[0].get('epsilon')
                
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
        total_randomizations_accumulated = 0
        k_val = 2 # Default
        
        # New Accumulator for Global Stats over all batches
        # Key: cond_key (path type), Value: {'success': 0, 'total': 0}
        global_path_stats = defaultdict(lambda: {'success': 0, 'total': 0})
        
        # Check metadata from first job to get constants and determine paths
        num_paths_per_instance = 1 # Default for dynamic
        
        if job_list:
            first_job = job_list[0]
            first_meta = first_job['metadata']
            
            # Handle nested pubs_metadata
            if 'pubs_metadata' in first_meta:
                # Use the first element of the list as representative metadata
                first_meta_content = first_meta['pubs_metadata'][0]
            else:
                first_meta_content = first_meta
                
            k_val = first_meta_content.get('k', 2)
            
            # Determine paths per instance for unrolled
            # Load the circuit metadata from the first job
            first_job_id = first_job['job_id']
            # Use source dir from the job record
            source_dir = first_job.get('_source_dir', args.job_dir)
            
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
            
            # Update randomizations count
            # Each metadata entry corresponds to a circuit. 
            # If we have P paths, we have P circuits per randomization instance (if unrolled fully).
            # So randomizations = len(batch_metadata) / num_paths_per_instance
            if not (batch_metadata and batch_metadata[0].get('type') == 'parameterized_unrolled'):
                if num_paths_per_instance > 0:
                    total_randomizations_accumulated += len(batch_metadata) / num_paths_per_instance
                else:
                    total_randomizations_accumulated += len(batch_metadata)
                
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
                    # Determine method
                    meta = job_record.get('metadata', {})
                    if 'pubs_metadata' in meta:
                        method = 'parameterized' # Implicitly
                        # Or check inside
                        if meta['pubs_metadata']:
                             method = meta['pubs_metadata'][0].get('type', 'parameterized').split('_')[0]
                    else:
                        method = meta.get('method', 'unrolled')
                        
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
                    
                    # For AER/Fake, we need to know if it was dynamic or unrolled to process correctly
                    # Usually, the result JSON structure differs, but extract_counts_from_job_result is not called here
                    # We loaded raw counts/quasi-dists from JSON.
                    # ResultProcessor methods expect specific format.
                    
                    # If dynamic, extracted_counts is usually a list of dicts (one per pub)
                    # The ResultProcessor.aggregate_batch_stats needs to know how to interpret keys.
                    pass
                
                else:
                    continue

                # Prepare total_clbits_list for processing
                # Estimate total bits from the first key in each count dictionary
                total_clbits_list = []
                
                # Check for Parameterized Unrolled
                is_parameterized = False
                if batch_metadata and batch_metadata[0].get('type') == 'parameterized_unrolled':
                    is_parameterized = True
                    
                    # Update Randomizations
                    # Sum num_randomizations from all paths in this job
                    # Note: For parameterized, each path entry in metadata has 'num_randomizations'.
                    # This number is M (randomizations per path).
                    # Since all paths in a job share the same randomizations (or same number),
                    # we should take the max or just one of them?
                    # No, total_randomizations_accumulated represents the total number of "Monte Carlo samples"
                    # used for the final fidelity average.
                    # In standard unrolled: we sum "randomization instances".
                    # Here, if we have M bindings, that is M instances.
                    # BUT, batch_metadata has P entries (one per path).
                    # Each entry says "num_randomizations": M.
                    # If we sum them, we get P * M. That's wrong.
                    # We want M.
                    # Wait, if we have multiple jobs, we sum M from each job.
                    # Inside a job, we have P paths. They all correspond to the SAME M randomizations (logically).
                    # So we should add M *only once* per job.
                    
                    if batch_metadata:
                        current_job_randomizations = batch_metadata[0].get('num_randomizations', 0)
                        total_randomizations_accumulated += current_job_randomizations

                    # Flatten Data for aggregation
                    # extracted_counts is [ [dict, dict...], [dict, dict...] ] (one list per path)
                    # batch_metadata is [ path1_meta, path2_meta ]
                    
                    flat_counts = []
                    flat_metadata = []
                    flat_clbits = []
                    
                    for i, path_counts_list in enumerate(extracted_counts):
                        # Ensure path_counts_list is a list
                        if isinstance(path_counts_list, dict):
                            path_counts_list = [path_counts_list]
                            
                        path_meta = batch_metadata[i]
                        
                        for counts in path_counts_list:
                            flat_counts.append(counts)
                            flat_metadata.append(path_meta)
                            if counts:
                                first_key = next(iter(counts))
                                flat_clbits.append(len(first_key.replace(" ", "")))
                            else:
                                flat_clbits.append(0)
                                
                    # Replace for downstream processing
                    extracted_counts = flat_counts
                    batch_metadata = flat_metadata
                    total_clbits_list = flat_clbits

                else:
                    # Standard Unrolled / Dynamic
                    for counts in extracted_counts:
                        if counts:
                            first_key = next(iter(counts))
                            total_clbits_list.append(len(first_key.replace(" ", "")))
                        else:
                            total_clbits_list.append(0)

                # Calculate Batch Stats and Accumulate
                # For dynamic circuits, we have a different aggregation logic
                # Determine method (Again, cleaner way?)
                meta = job_record.get('metadata', {})
                if 'pubs_metadata' in meta:
                    method = 'parameterized'
                else:
                    method = meta.get('method', 'unrolled')
                
                if method == 'dynamic':
                    # Dynamic: Single circuit result, but split into "paths" logically?
                    # No, dynamic result is a single distribution.
                    # process_dynamic_result returns a single fidelity number.
                    # But here we want to aggregate.
                    
                    # For dynamic, we don't have "paths" in the same way.
                    # We have a single fidelity value per shot? Or per circuit?
                    # ResultProcessor.process_dynamic_result calculates Fidelity = P(success)
                    # P(success) = counts(success_state) / total_shots
                    
                    # To fit into global_path_stats structure:
                    # We can treat it as a single "path_dynamic"
                    # Success = counts(success_state), Total = total_shots
                    
                    # We need to parse the counts to find success state
                    # Success state is when all ancilla measurements are 0?
                    # Dynamic circuit builder measures final state to 'readout'
                    # But intermediate failures are handled by if_test.
                    # If failed, we don't measure final? Or we measure garbage?
                    
                    # Wait, dynamic circuit builder:
                    # If success -> measure reserve to readout
                    # If fail -> do nothing (so readout is 0?)
                    # Actually, let's look at process_dynamic_result in ResultProcessor
                    
                    # Re-implement logic here to aggregate:
                    # We need to know which keys correspond to "Success"
                    # But process_dynamic_result does it all at once.
                    
                    # Let's just accumulate the counts directly?
                    # extracted_counts is [ {counts} ]
                    
                    counts = extracted_counts[0]
                    total_shots = sum(counts.values())
                    
                    # We need to identify success keys.
                    # This depends on ResultProcessor logic.
                    # Let's instantiate processor to use its helper if possible, or replicate logic.
                    
                    # Replicating logic from ResultProcessor.process_dynamic_result for aggregation
                    # success_key is when all relevant bits are correct.
                    # But dynamic circuit usually only produces output on success?
                    # Or it produces output always?
                    
                    # In DynamicCircuitBuilder:
                    # qc.measure(initial_reserve, cr_final) is at the end.
                    # But it's only reached if recursion completes?
                    # No, it's sequential. But the recursive layers are conditional.
                    # If a branch fails, the subsequent code in 'else' or skipped 'if' is not executed.
                    # So if purification fails, we might not reach the final measurement?
                    # If we don't reach measure, the classical bits are 0.
                    
                    # So '0' could mean "measured 0" OR "didn't measure".
                    # This is ambiguous if 0 is a valid state.
                    # But typically we purify to |0...0> + |1...1> (GHZ) or Bell pair.
                    # If we purify Bell pair |00>+|11>, valid outcomes are 00, 11.
                    # If we fail, we might get 00 by default?
                    
                    # Let's assume ResultProcessor handles this.
                    # Since we want to aggregate, we can just sum up the counts
                    # global_dynamic_counts += counts
                    # And then process at the end?
                    
                    # Simpler approach: Calculate fidelity per batch, then average?
                    # But we want error bars.
                    # Let's treat "dynamic" as one single path.
                    
                    fid = processor.process_dynamic_result(counts, total_clbits_list[0])
                    # fid is success_prob
                    n_succ = int(fid * total_shots)
                    
                    global_path_stats['dynamic']['success'] += n_succ
                    global_path_stats['dynamic']['total'] += total_shots
                    
                else:
                    # Unrolled
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
                     
                     if method == 'dynamic':
                         print(f"DEBUG: Dynamic Batch -> Success: {n_succ}, Total: {total_shots}, Fid: {fid:.4f}")
                     else:
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
        
        # New Error Estimation: sqrt(Var_statistical + Var_systematic)
        # Var_statistical = variance_sum (Standard Error of Mean squared)
        # Var_systematic = (fidelity * lambda / sqrt(N_total))^2
        
        systematic_error_sq = 0.0
        if total_randomizations_accumulated > 0:
            systematic_error_sq = (final_fid * epsilon / np.sqrt(total_randomizations_accumulated)) ** 2
            
        total_error = np.sqrt(variance_sum + systematic_error_sq)
        
        print(f"Lambda={epsilon:.4f} -> Fidelity={final_fid:.4f} +/- {total_error:.4f} (Batches: {successful_batches}/{len(job_list)})")
        results_data.append({'lambda': epsilon, 'fidelity': final_fid, 'error': total_error})

    # Save
    df = pd.DataFrame(results_data)
    df.to_csv(args.output, index=False)
    print(f"Saved retrieved results to {args.output}")

if __name__ == "__main__":
    main()
