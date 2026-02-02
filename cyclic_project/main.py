import argparse
import sys
import os
import pandas as pd
import numpy as np
from tqdm import tqdm
from collections import Counter

from core.circuit_builder import DynamicCircuitBuilder, UnrolledCircuitBuilder
from core.noise_models import StandardDepolarizingStrategy, PauliTwirlingStrategy
from execution.backend_handler import AERHandler, FakeBackendHandler, IBMRuntimeHandler
from execution.job_manager import JobManager
from analysis.result_processor import ResultProcessor

def main():
    parser = argparse.ArgumentParser(description="QPA Modular Simulation")
    parser.add_argument('--backend', type=str, choices=['aer', 'fake', 'ibm'], default='aer', help="Target backend type")
    parser.add_argument('--device', type=str, default='ibm_brisbane', help="Specific device name (for fake/ibm)")
    
    # Method selection: Dynamic (default for AER) or Unrolled (default for Hardware)
    parser.add_argument('--method', type=str, choices=['dynamic', 'unrolled', 'auto'], default='auto', 
                        help="Circuit generation method. 'auto' chooses based on backend.")

    # QPA Parameters
    parser.add_argument('--n', type=int, default=5, help="Number of registers (must be odd)")
    parser.add_argument('--k', type=int, default=2, help="Qubits per register")
    parser.add_argument('--trials', type=int, default=3, help="Number of QPA trials (depth)")
    
    # Noise Sweep
    parser.add_argument('--lambda-min', type=float, default=0.0, help="Min noise")
    parser.add_argument('--lambda-max', type=float, default=1.0, help="Max noise")
    parser.add_argument('--points', type=int, default=5, help="Number of lambda points")
    parser.add_argument('--n-random', type=int, default=1, help="Number of random Pauli instances per circuit")
    
    # Execution
    parser.add_argument('--shots', type=int, default=10000, help="Shots per circuit")
    parser.add_argument('--dry-run', action='store_true', help="Do not submit jobs")
    parser.add_argument('--post-only', action='store_true', help="Submit jobs to IBM and exit (do not wait for results)")
    parser.add_argument('--output', type=str, default='results.csv', help="Output CSV file")
    
    # Advanced Execution Control
    parser.add_argument('--batch-size', type=int, default=50, help="Batch size for submission. -1 for all at once.")
    parser.add_argument('--slurm-task-id', type=int, default=None, help="SLURM array task ID (0-based) to select a single lambda.")
    parser.add_argument('--slurm-num-tasks', type=int, default=None, help="Total number of SLURM tasks (for validation).")
    
    args = parser.parse_args()

    # Determine Method
    if args.method == 'auto':
        if args.backend == 'aer':
            method = 'dynamic'
        else:
            method = 'unrolled'
    else:
        method = args.method

    print(f"\n--- QPA Simulation Config ---")
    print(f"Backend: {args.backend} ({args.device})")
    print(f"Method:  {method}")
    print(f"Topology: N={args.n}, K={args.k}, Trials={args.trials}")
    print(f"Noise: [{args.lambda_min}, {args.lambda_max}] ({args.points} points)")
    print(f"Twirling: {args.n_random} instances")
    
    # 1. Initialize Components
    if args.backend == 'aer':
        backend_handler = AERHandler()
        # On AER:
        # If dynamic -> StandardDepolarizing (native simulator noise)
        # If unrolled -> PauliTwirling (mimic hardware noise)
        if method == 'dynamic':
            builder = DynamicCircuitBuilder(args.k, args.trials, args.n)
            noise_cls = StandardDepolarizingStrategy
            is_dynamic = True
        else:
            builder = UnrolledCircuitBuilder(args.k, args.trials, args.n)
            noise_cls = PauliTwirlingStrategy
            is_dynamic = False
            
    elif args.backend == 'fake':
        backend_handler = FakeBackendHandler(args.device)
        builder = UnrolledCircuitBuilder(args.k, args.trials, args.n)
        noise_cls = PauliTwirlingStrategy
        is_dynamic = False
        if method == 'dynamic':
            print("Warning: Fake backends typically do not support dynamic circuits well. Forcing unrolled.")
            
    else: # ibm
        backend_handler = IBMRuntimeHandler(backend_name=args.device)
        builder = UnrolledCircuitBuilder(args.k, args.trials, args.n)
        noise_cls = PauliTwirlingStrategy
        is_dynamic = False

    # Ensure data/jobs directory is relative to project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    jobs_dir = os.path.join(project_root, "data", "jobs")
    
    job_manager = JobManager(backend_handler, output_dir=jobs_dir)
    result_processor = ResultProcessor(args.k)
    
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.points)
    
    # SLURM Array Logic: Select specific lambda if task_id is provided
    if args.slurm_task_id is not None:
        if args.slurm_task_id < 0 or args.slurm_task_id >= len(lambdas):
            print(f"Error: SLURM task ID {args.slurm_task_id} is out of range for {len(lambdas)} lambda points.")
            sys.exit(1)
            
        print(f"SLURM Array Mode: Processing task {args.slurm_task_id}/{len(lambdas)-1}")
        lambdas = [lambdas[args.slurm_task_id]]
        
        # Modify output filename to prevent collisions
        base, ext = os.path.splitext(args.output)
        args.output = f"{base}_task{args.slurm_task_id}{ext}"
        print(f"Output file set to: {args.output}")

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    results_data = []

    print("\n--- Starting Execution Loop ---")
    for epsilon in tqdm(lambdas):
        
        # Prepare Batch
        batch_circuits = []
        batch_metadata = [] # Stores conditions for each circuit
        
        # Determine number of instances
        # Dynamic: usually 1 instance (noise handled by simulator)
        # Unrolled: n_random instances (noise handled by random gates)
        total_instances = args.n_random if not is_dynamic else 1
        
        # Calculate shots per circuit to maintain total shots constant
        shots_per_circuit = max(1, args.shots // total_instances)
        if total_instances > 1:
            print(f"Splitting {args.shots} total shots across {total_instances} randomizations -> {shots_per_circuit} shots/circuit")
        
        # Batching Strategy for Memory Safety
        if args.batch_size == -1:
             BATCH_SIZE = total_instances
             print(f"Batching disabled: Submitting all {total_instances} instances in one batch.")
        else:
             BATCH_SIZE = args.batch_size  # Process instances in chunks
             
        aggregated_fidelity_sum = 0.0
        
        # Split instances into chunks
        num_batches = (total_instances + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_idx in range(num_batches):
            current_batch_size = min(BATCH_SIZE, total_instances - batch_idx * BATCH_SIZE)
            
            batch_circuits = []
            batch_metadata = [] # Stores conditions for each circuit
            
            for _ in range(current_batch_size):
                # Re-initialize noise strategy to get fresh random seed if needed
                noise_strategy = noise_cls(args.k)
                builder.set_noise_strategy(noise_strategy)
                
                # Build circuits (1 for Dynamic, Many for Unrolled)
                circuits_data = builder.build(epsilon)
                
                for item in circuits_data:
                    batch_circuits.append(item['circuit'])
                    batch_metadata.append(item) # Contains 'conditions'
            
            # Submit Batch
            try:
                job_info = job_manager.submit_batch(
                    batch_circuits, 
                    shots=shots_per_circuit, 
                    job_tags=[f"n{args.n}", f"k{args.k}", f"lam{epsilon:.4f}", f"batch{batch_idx}"],
                    metadata={
                        'epsilon': epsilon, 
                        'batch_idx': batch_idx,
                        'total_instances': total_instances,
                        'shots_per_circuit': shots_per_circuit,
                        'n_registers': args.n,
                        'k': args.k,
                        'method': method
                    },
                    dry_run=args.dry_run
                )
                
                # Save batch_metadata (conditions) for later retrieval
                # We need this because result processing depends on knowing the post-selection conditions
                if not args.dry_run:
                    job_id = job_info['job_id']
                    meta_path = os.path.join(job_manager.output_dir, f"{job_id}_circuit_meta.json")
                    
                    # Prepare serializable metadata (remove circuit objects)
                    serializable_meta = []
                    for item in batch_metadata:
                        # Copy item but exclude 'circuit'
                        clean_item = {k: v for k, v in item.items() if k != 'circuit'}
                        serializable_meta.append(clean_item)
                        
                    import json
                    with open(meta_path, 'w') as f:
                        json.dump(serializable_meta, f)
                    
            except Exception as e:
                print(f"Submission failed for batch {batch_idx}: {e}")
                continue
            
            if args.dry_run:
                continue

            if args.post_only:
                print(f"Job submitted (Post-Only). ID: {job_info['job_id']}")
                # We don't process results or append to results_data in this mode.
                # The JobManager has already saved the job record to job_history.jsonl
                continue

            # Process Results
            try:
                job = job_info['job_object']
                pub_result = job.result() 
                
                extracted_counts = []
                total_clbits_list = []
                
                # SamplerV2 Result Processing
                # Each element in pub_result corresponds to one circuit in the batch
                for i, pub_res in enumerate(pub_result):
                    data = pub_res.data
                    
                    # Check for available registers
                    # We prioritize 'anc_meas' + 'readout' for Unrolled
                    # And just 'readout' for Dynamic
                    
                    has_anc = hasattr(data, 'anc_meas')
                    has_read = hasattr(data, 'readout')
                    
                    if not is_dynamic and has_anc and has_read:
                        # Unrolled: Merge 'anc_meas' (MSB) and 'readout' (LSB)
                        
                        # Handle case where anc_meas is empty (e.g. n_trials=0)
                        if data.anc_meas.num_bits == 0:
                            # Only readout matters
                            read_strs = data.readout.get_bitstrings()
                            extracted_counts.append(dict(Counter(read_strs)))
                            total_clbits_list.append(len(read_strs[0]))
                        else:
                            anc_strs = data.anc_meas.get_bitstrings()
                            read_strs = data.readout.get_bitstrings()
                            
                            merged = [a + r for a, r in zip(anc_strs, read_strs)]
                            extracted_counts.append(dict(Counter(merged)))
                            total_clbits_list.append(len(merged[0]))
                        
                    elif hasattr(data, 'meas'): 
                        # Fallback: if measure_all() was used or single register
                        extracted_counts.append(data.meas.get_counts())
                        # Estimate total bits from first key
                        first_key = next(iter(extracted_counts[-1]))
                        total_clbits_list.append(len(first_key))
                        
                    elif has_read:
                        # Dynamic or simple readout
                        extracted_counts.append(data.readout.get_counts())
                        first_key = next(iter(extracted_counts[-1]))
                        total_clbits_list.append(len(first_key))
                        
                    else:
                        # Fallback: try to find any BitArray
                        found = False
                        for attr in dir(data):
                            if not attr.startswith('_'):
                                val = getattr(data, attr)
                                if hasattr(val, 'get_counts'):
                                    extracted_counts.append(val.get_counts())
                                    first_key = next(iter(extracted_counts[-1]))
                                    total_clbits_list.append(len(first_key))
                                    found = True
                                    break
                        if not found:
                            print(f"Warning: No valid measurements found for circuit {i}")
                            extracted_counts.append({})
                            total_clbits_list.append(0)

                # Calculate Fidelity for this Batch
                if not is_dynamic:
                    # Unrolled: Aggregates multiple paths
                    batch_fid = result_processor.process_unrolled_results(extracted_counts, batch_metadata, total_clbits_list)
                    
                    # NOTE: process_unrolled_results returns the sum of (successes/shots) for all instances in the list
                    # It treats the input list as "one large experiment".
                    # Since we feed it `current_batch_size` instances, it sums them all up.
                    # We want to accumulate this sum.
                    aggregated_fidelity_sum += batch_fid
                    
                else:
                    # Dynamic: Single circuit
                    fid = result_processor.process_dynamic_result(extracted_counts[0], total_clbits_list[0])
                    aggregated_fidelity_sum += fid

            except Exception as e:
                print(f"Error processing results: {e}")
                import traceback
                traceback.print_exc()
        
        # Final Average Fidelity Calculation
        if args.dry_run or args.post_only:
            final_fid = 0.0
        else:
            # We divide by total_instances to get the average
            final_fid = aggregated_fidelity_sum / total_instances

        if not args.post_only:
            print(f"Lambda={epsilon:.4f} -> Fidelity={final_fid:.4f}")
            results_data.append({'lambda': epsilon, 'fidelity': final_fid})

    # Save to CSV
    if not args.dry_run and not args.post_only:
        df = pd.DataFrame(results_data)
        df.to_csv(args.output, index=False)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
