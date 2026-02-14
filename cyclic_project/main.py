import argparse
import sys
import os
import pandas as pd
import numpy as np
from tqdm import tqdm
from collections import Counter
from qiskit import transpile
from qiskit.circuit import CircuitInstruction
from qiskit.circuit.library import XGate, RZGate

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
    
    # Structure: data/jobs/<backend>/<device>/n<N>_k<K>_t<Trials>/p<Points>/s<Shots>_c<Random>/<timestamp>
    param_str = f"n{args.n}_k{args.k}_t{args.trials}"
    points_str = f"p{args.points}"
    config_str = f"s{args.shots}_c{args.n_random}"
    timestamp_str = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # If backend is aer, device defaults to ibm_brisbane but it is simulated.
    # We should probably respect args.device even for aer if it's set.
    if args.backend == 'aer':
        if args.device == 'ibm_brisbane':
            # If user didn't specify a device for AER, decide based on method
            if method == 'dynamic':
                device_name = 'aer_dynamic'
            else:
                device_name = 'aer_unrolled'
        else:
            # If user specified a device, keep it but maybe append method if they want separation
            # Or trust the user. Let's append method to avoid collision if they use same device name for both.
            device_name = f"{args.device}_{method}"
    else:
        device_name = args.device

    jobs_dir = os.path.join(project_root, "data", "jobs", args.backend, device_name, param_str, points_str, config_str, timestamp_str)
    
    # Ensure directory exists
    os.makedirs(jobs_dir, exist_ok=True)
    
    # Define history_dir as .../pXX (2 levels up from jobs_dir which is .../timestamp)
    # jobs_dir: .../pXX/sXX_cXX/timestamp
    # history_dir: .../pXX
    try:
        parent_dir = os.path.dirname(jobs_dir) # .../sXX_cXX
        history_dir = os.path.dirname(parent_dir) # .../pXX
        
        # Verify it looks like a pXX directory to be safe, otherwise default to jobs_dir
        if not os.path.basename(history_dir).startswith('p'):
             print(f"Warning: Computed history dir {history_dir} does not start with 'p', defaulting to {jobs_dir}")
             history_dir = jobs_dir
    except:
        history_dir = jobs_dir

    job_manager = JobManager(backend_handler, output_dir=jobs_dir, history_dir=history_dir)
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

    # --- OPTIMIZATION: Transpile Once, Patch Many (for Unrolled + PauliTwirling) ---
    # We only enable this if we are doing Unrolled method on a backend that needs transpilation (IBM/Fake/AER)
    # AND the noise strategy is PauliTwirling (which allows patching).
    use_fast_path = (method == 'unrolled' and args.backend in ['ibm', 'fake', 'aer'] and noise_cls == PauliTwirlingStrategy)
    
    transpiled_golden_circuits = []
    golden_metadata = []
    
    if use_fast_path:
        print("\n--- Pre-Transpiling Golden Circuits (Optimization) ---")
        # 1. Build Golden Circuits (No Noise)
        # We need to ensure no noise is applied during build
        builder.set_noise_strategy(None)
        golden_data = builder.build(0.0)
        
        golden_circuits = [item['circuit'] for item in golden_data]
        golden_metadata = [{k:v for k,v in item.items() if k!='circuit'} for item in golden_data]
        
        # 2. Transpile with High Optimization
        print(f"Transpiling {len(golden_circuits)} golden circuits with optimization_level=3...")
        
        # Determine parallel cores for transpilation
        try:
            num_cores = len(os.sched_getaffinity(0))
        except AttributeError:
            num_cores = os.cpu_count() or 1
            
        transpiled_golden_circuits = transpile(
            golden_circuits, 
            backend=job_manager.backend, 
            optimization_level=3,
            num_processes=num_cores
        )
        if not isinstance(transpiled_golden_circuits, list):
            transpiled_golden_circuits = [transpiled_golden_circuits]
            
        print("Golden circuits transpiled.")

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
             # Handle negative batch size error if user inputs weirdly, but here assuming positive
             if args.batch_size <= 0:
                 print(f"Warning: Invalid batch size {args.batch_size}, defaulting to 50")
                 BATCH_SIZE = 50
             else:
                 BATCH_SIZE = args.batch_size
             
        aggregated_fidelity_sum = 0.0
        
        # Split instances into chunks
        num_batches = (total_instances + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_idx in range(num_batches):
            current_batch_size = min(BATCH_SIZE, total_instances - batch_idx * BATCH_SIZE)
            
            batch_circuits = []
            batch_metadata = [] # Stores conditions for each circuit
            
            # --- FAST PATH vs SLOW PATH ---
            if use_fast_path:
                # Fast Path: Patch Transpiled Circuits
                # We reuse the transpiled golden circuits and patch them with random Pauli gates
                
                # Set optimization_level to 0 for submission since we are already transpiled/patched
                submit_opt_level = 0
                skip_transpilation = True
                
                # Pre-calculate noise registers from the first golden circuit (structure is same)
                # We need the Qubit objects from the original golden circuits to map to physical
                # We can do this per path.
                
                # Iterate over instances in this batch
                for _ in range(current_batch_size):
                    noise_strategy = noise_cls(args.k) # New strategy instance (fresh randomness)
                    
                    # For each path in the decision tree
                    for i, qc_transpiled in enumerate(transpiled_golden_circuits):
                         # Create a shallow copy of the transpiled circuit
                         # NOTE: copy() is shallow enough that instructions are shared but list is new
                         qc_instance = qc_transpiled.copy()
                         
                         # Get original circuit to find logical registers
                         orig_qc = golden_circuits[i]
                         
                         # Identify Data Registers (R1, R2, ...)
                         # We only apply noise to data registers as per PauliTwirlingStrategy
                         data_regs = [reg for reg in orig_qc.qregs if reg.name.startswith("R")]
                         
                         # Generate Noise Operations (Logical)
                         noise_ops = noise_strategy.generate_noise_ops(data_regs, epsilon)
                         
                         # Apply to Physical Qubits using Layout
                         layout = None
                         if qc_transpiled.layout:
                             layout = qc_transpiled.layout.initial_layout
                         
                         for gate, logical_qubit in noise_ops:
                             target_qubit = None
                             
                             if layout and logical_qubit in layout:
                                 phys_qubit_idx = layout[logical_qubit]
                                 target_qubit = qc_instance.qubits[phys_qubit_idx]
                             elif logical_qubit in qc_instance.qubits:
                                 # No layout change (e.g. Aer), qubit preserved
                                 target_qubit = logical_qubit
                             else:
                                 # Try to match by register name/index if object is different
                                 for q in qc_instance.qubits:
                                     # Check safely if register attributes match
                                     if hasattr(q, 'register') and hasattr(logical_qubit, 'register'):
                                         if q.register.name == logical_qubit.register.name and \
                                            q.index == logical_qubit.index:
                                             target_qubit = q
                                             break
                                     # Fallback for older Qiskit versions or different object structure
                                     elif hasattr(q, '_register') and hasattr(logical_qubit, '_register'):
                                          if q._register.name == logical_qubit._register.name and \
                                             q._index == logical_qubit._index:
                                              target_qubit = q
                                              break
                             
                             if target_qubit:
                                 # Insert gate at the beginning (State Preparation Noise)
                                 # Check if we need to decompose for ISA compliance (only if skipping transpilation on IBM/Fake)
                                 # Standard IBM Basis: ['rz', 'sx', 'x', 'ecr', 'id'] (or 'cx')
                                 if args.backend in ['ibm', 'fake'] and skip_transpilation:
                                     if gate.name == 'z':
                                         # Z -> RZ(pi)
                                         qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                     elif gate.name == 'y':
                                         # Y -> RZ(pi) X (applied X then RZ(pi) -> Y)
                                         # Insert in reverse order of application because we are prepending
                                         # We want effectively: |psi> -> X -> RZ(pi) -> |psi'>
                                         # insert(0, X) -> [X, ...]
                                         # insert(0, RZ) -> [RZ, X, ...] (RZ applied FIRST? No. Wait.)
                                         
                                         # CircuitInstruction logic:
                                         # data = [op1, op2, ...]
                                         # insert(0, new_op) -> [new_op, op1, op2, ...]
                                         # Execution: new_op, then op1.
                                         
                                         # We want X applied first, then RZ(pi).
                                         # So we need sequence in data list: [X, RZ(pi), original...]
                                         # 1. Insert RZ(pi) at 0 -> [RZ, original...]
                                         # 2. Insert X at 0 -> [X, RZ, original...]
                                         qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                         qc_instance.data.insert(0, CircuitInstruction(XGate(), (target_qubit,), ()))
                                     else:
                                         # X or I (X is usually native or handled, I is identity)
                                         qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                                 else:
                                     qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                             else:
                                 pass # Qubit not found (should not happen if noise_ops generated from valid regs)
                         
                         batch_circuits.append(qc_instance)
                         batch_metadata.append(golden_metadata[i])
                
            else:
                # Slow Path: Re-build and Re-transpile every time
                submit_opt_level = None # Let job_manager decide (usually 3 or 1)
                skip_transpilation = False
                
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
                    dry_run=args.dry_run,
                    optimization_level=submit_opt_level,
                    skip_transpilation=skip_transpilation
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
                
                extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                
                # Prepare total_clbits_list for processing
                total_clbits_list = []
                for counts in extracted_counts:
                    if counts:
                        first_key = next(iter(counts))
                        total_clbits_list.append(len(first_key.replace(" ", "")))
                    else:
                        total_clbits_list.append(0)

                # Calculate Fidelity for this Batch
                if not is_dynamic:
                    # Unrolled: Aggregates multiple paths
                    batch_fid = result_processor.process_unrolled_results(extracted_counts, batch_metadata, total_clbits_list)
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
        
        # Flush stdout to ensure logs appear in real-time
        sys.stdout.flush()

    # Save to CSV
    if not args.dry_run and not args.post_only:
        df = pd.DataFrame(results_data)
        df.to_csv(args.output, index=False)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
