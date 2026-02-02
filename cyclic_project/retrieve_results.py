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
    parser.add_argument('--job-dir', type=str, default='data/jobs', help="Directory with job history")
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
    else:
        print("AER backend does not support persistent job retrieval.")
        return

    # 2. Load Job History
    # Ensure job_dir is absolute
    if not os.path.isabs(args.job_dir):
        # Assume relative to project root if not absolute?
        # Or relative to CWD?
        # main.py now uses absolute path: project_root/data/jobs
        # So we should default to that if default is used.
        if args.job_dir == 'data/jobs':
             project_root = os.path.dirname(os.path.abspath(__file__))
             args.job_dir = os.path.join(project_root, "data", "jobs")
        else:
             args.job_dir = os.path.abspath(args.job_dir)
             
    history_file = os.path.join(args.job_dir, "job_history.jsonl")
    all_jobs = load_job_history(history_file)
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
        
        # Check metadata from first job to get constants
        if job_list:
            first_meta = job_list[0]['metadata']
            k_val = first_meta.get('k', 2)
            
        processor = ResultProcessor(k_val)
        
        successful_batches = 0
        
        for job_record in job_list:
            job_id = job_record['job_id']
            
            # Load Circuit Metadata (Conditions)
            meta_path = os.path.join(args.job_dir, f"{job_id}_circuit_meta.json")
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
                    
                elif args.backend == 'fake':
                    # Load from local result JSON
                    result_path = os.path.join(args.job_dir, f"{job_id}_result.json")
                    if not os.path.exists(result_path):
                        print(f"Result file not found for fake job {job_id}, skipping.")
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

                # Calculate Batch Fidelity
                batch_fid = processor.process_unrolled_results(extracted_counts, batch_metadata, total_clbits_list)
                aggregated_fidelity_sum += batch_fid
                
                # Update total accumulated circuits
                total_circuits_accumulated += len(extracted_counts)
                successful_batches += 1
                
            except Exception as e:
                print(f"Failed to retrieve/process job {job_id}: {e}")
                
        if total_circuits_accumulated > 0:
            final_fid = aggregated_fidelity_sum / total_circuits_accumulated
        else:
            final_fid = 0.0
            
        print(f"Lambda={epsilon:.4f} -> Fidelity={final_fid:.4f} (Batches: {successful_batches}/{len(job_list)}, Total Circuits: {total_circuits_accumulated})")
        results_data.append({'lambda': epsilon, 'fidelity': final_fid})

    # Save
    df = pd.DataFrame(results_data)
    df.to_csv(args.output, index=False)
    print(f"Saved retrieved results to {args.output}")

if __name__ == "__main__":
    main()
