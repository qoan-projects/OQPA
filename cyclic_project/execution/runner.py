import concurrent.futures
import multiprocessing as mp
import json
import os
import sys
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from tqdm import tqdm
from qiskit import transpile
from qiskit.circuit import CircuitInstruction
from qiskit.circuit.library import XGate, RZGate

from core.circuit_factory import CircuitFactory
from core.noise_models import StandardDepolarizingStrategy, PauliTwirlingStrategy
from execution.job_service import JobService
from execution.transpiler_service import TranspilerService
from execution.backend_handler import AERHandler, FakeBackendHandler, IBMRuntimeHandler
from analysis.result_processor import ResultProcessor
from utils.config import SimulationConfig
from utils.paths import PathManager

def run_simulation_point_wrapper(params):
    """
    Wrapper to unpack arguments for run_simulation_point.
    params: (epsilon, config, jobs_dir, history_dir)
    """
    epsilon, config, jobs_dir, history_dir = params
    return run_simulation_point(epsilon, config, jobs_dir, history_dir)

def run_simulation_point(epsilon: float, config: SimulationConfig, jobs_dir: str, history_dir: str):
    """
    Worker function to run simulation for a single lambda point.
    Re-instantiates necessary components to avoid pickling issues and ensure thread safety.
    """
    # Re-init components
    if config.backend == 'aer':
        backend_handler = AERHandler()
        if config.method == 'dynamic':
            noise_cls = StandardDepolarizingStrategy
            is_dynamic = True
        else:
            noise_cls = PauliTwirlingStrategy
            is_dynamic = False
    elif config.backend == 'fake':
        backend_handler = FakeBackendHandler(config.device)
        noise_cls = PauliTwirlingStrategy
        is_dynamic = False
    else:
        return None

    # Instantiate Builder via Factory
    # Note: Factory returns Strategy, which builds circuits
    strategy = CircuitFactory.create_strategy(config.method, config.k, config.trials, config.n)
    
    # Initialize JobService
    job_service = JobService(backend_handler, output_dir=jobs_dir, history_dir=history_dir)
    result_processor = ResultProcessor(config.k)
    
    # Disable nested parallelism in worker
    # Ensure we pass the backend object, not a method
    backend_obj = job_service.sampler.backend if hasattr(job_service.sampler, 'backend') and not callable(job_service.sampler.backend) else backend_handler.get_backend()
    
    transpiler_service = TranspilerService(
        backend_obj,
        num_processes=1
    )

    total_instances = config.n_random if not is_dynamic else 1
    shots_per_circuit = max(1, config.shots // total_instances)
    
    if config.batch_size == -1:
        BATCH_SIZE = total_instances
    else:
        BATCH_SIZE = config.batch_size if config.batch_size > 0 else 50
        
    global_path_stats = defaultdict(lambda: {'success': 0, 'total': 0})
    global_dynamic_stats = {'success': 0, 'total': 0}
    job_records = []
    
    # Optimization: Fast Path for Unrolled + PauliTwirling
    use_fast_path = (config.method == 'unrolled' and config.backend in ['ibm', 'fake', 'aer'] and noise_cls == PauliTwirlingStrategy)
    
    transpiled_golden_circuits = []
    golden_metadata = []
    golden_circuits = []

    if use_fast_path:
        # Pre-Transpiling Golden Circuits (Optimization)
        strategy.set_noise_strategy(None)
        golden_data = strategy.build(0.0)
        golden_circuits = [item['circuit'] for item in golden_data]
        golden_metadata = [{k:v for k,v in item.items() if k!='circuit'} for item in golden_data]
        
        transpiled_golden_circuits = transpiler_service.transpile(golden_circuits)
        if not isinstance(transpiled_golden_circuits, list):
            transpiled_golden_circuits = [transpiled_golden_circuits]

    num_batches = (total_instances + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_idx in range(num_batches):
        current_batch_size = min(BATCH_SIZE, total_instances - batch_idx * BATCH_SIZE)
        
        batch_circuits = []
        batch_metadata = []
        skip_transpilation = False
        
        if use_fast_path:
            skip_transpilation = True
            for _ in range(current_batch_size):
                noise_strategy = noise_cls(config.k)
                for i, qc_transpiled in enumerate(transpiled_golden_circuits):
                    qc_instance = qc_transpiled.copy()
                    # Need original qc to know registers for noise ops
                    orig_qc = golden_circuits[i]
                    # Assuming Register names start with R...
                    data_regs = [reg for reg in orig_qc.qregs if reg.name.startswith("R")]
                    noise_ops = noise_strategy.generate_noise_ops(data_regs, epsilon)
                    
                    # Apply noise ops to transpiled circuit
                    layout = qc_transpiled.layout.initial_layout if qc_transpiled.layout else None
                    
                    for gate, logical_qubit in noise_ops:
                        target_qubit = None
                        if layout and logical_qubit in layout:
                            phys_qubit_idx = layout[logical_qubit]
                            target_qubit = qc_instance.qubits[phys_qubit_idx]
                        elif logical_qubit in qc_instance.qubits:
                            target_qubit = logical_qubit
                        else:
                            # Fallback search
                            for q in qc_instance.qubits:
                                if hasattr(q, 'register') and hasattr(logical_qubit, 'register'):
                                        if q.register.name == logical_qubit.register.name and q.index == logical_qubit.index:
                                            target_qubit = q
                                            break
                                elif hasattr(q, '_register') and hasattr(logical_qubit, '_register'):
                                    if q._register.name == logical_qubit._register.name and q._index == logical_qubit._index:
                                        target_qubit = q
                                        break
                        
                        if target_qubit:
                            # Insert gate at beginning
                            if config.backend in ['ibm', 'fake']:
                                # Convert Pauli to ISA-safe gates if needed (RZ(pi) for Z, etc)
                                if gate.name == 'z':
                                    qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                elif gate.name == 'y':
                                    qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                    qc_instance.data.insert(0, CircuitInstruction(XGate(), (target_qubit,), ()))
                                else:
                                    qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                            else:
                                qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                    
                    batch_circuits.append(qc_instance)
                    batch_metadata.append(golden_metadata[i])
            
            transpiled_circuits = batch_circuits

        else:
            # SLOW PATH (re-build)
            for _ in range(current_batch_size):
                noise_strategy = noise_cls(config.k)
                strategy.set_noise_strategy(noise_strategy)
                circuits_data = strategy.build(epsilon)
                
                for item in circuits_data:
                    batch_circuits.append(item['circuit'])
                    batch_metadata.append(item)

            # Transpile
            transpiled_circuits = transpiler_service.transpile(batch_circuits)

        # Submit Batch
        try:
            job_info = job_service.submit_batch(
                transpiled_circuits, 
                shots=shots_per_circuit, 
                job_tags=[f"n{config.n}", f"k{config.k}", f"lam{epsilon:.4f}", f"batch{batch_idx}"],
                metadata={
                    'epsilon': epsilon, 
                    'batch_idx': batch_idx,
                    'total_instances': total_instances,
                    'shots_per_circuit': shots_per_circuit,
                    'n_registers': config.n,
                    'k': config.k,
                    'method': config.method
                },
                dry_run=config.dry_run,
                save_history=False 
            )
            
            if 'record' in job_info:
                job_records.append(job_info['record'])
            
            # Save metadata json
            if not config.dry_run:
                job_id = job_info['job_id']
                job_service.save_circuit_metadata(job_id, batch_metadata)
            
            # Special handling for local backends: save results even in post-only mode
            extracted_counts = None
            if config.backend in ['aer', 'fake'] and not config.dry_run:
                job = job_info['job_object']
                pub_result = job.result()
                extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                job_service.save_local_results(job_info['job_id'], extracted_counts)

            if config.dry_run or config.post_only:
                continue

            # Process Results
            if extracted_counts is None:
                job = job_info['job_object']
                pub_result = job.result()
                extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                
                # Save local results if needed (for consistency with parallel mode)
                job_service.save_local_results(job_info['job_id'], extracted_counts)

            total_clbits_list = []
            for counts in extracted_counts:
                if counts:
                    first_key = next(iter(counts))
                    total_clbits_list.append(len(first_key.replace(" ", "")))
                else:
                    total_clbits_list.append(0)

            if not is_dynamic:
                batch_stats = result_processor.aggregate_batch_stats(extracted_counts, batch_metadata, total_clbits_list)
                for cond_key, stats in batch_stats.items():
                    global_path_stats[cond_key]['success'] += stats['success']
                    global_path_stats[cond_key]['total'] += stats['total']
            else:
                fid = result_processor.process_dynamic_result(extracted_counts[0], total_clbits_list[0])
                total = sum(extracted_counts[0].values())
                succ = int(fid * total + 0.5)
                global_dynamic_stats['success'] += succ
                global_dynamic_stats['total'] += total

        except Exception as e:
            print(f"Error in parallel worker for epsilon={epsilon}: {e}")
            import traceback
            traceback.print_exc()
            
    final_fid = 0.0
    if not (config.dry_run or config.post_only):
        if not is_dynamic:
            for stats in global_path_stats.values():
                 if stats['total'] > 0:
                     final_fid += stats['success'] / stats['total']
        else:
            if global_dynamic_stats['total'] > 0:
                final_fid = global_dynamic_stats['success'] / global_dynamic_stats['total']
    
    return {
        'epsilon': epsilon,
        'fidelity': final_fid,
        'records': job_records
    }

class SimulationRunner:
    def __init__(self, config: SimulationConfig):
        self.config = config
        
        # Determine directories
        self.jobs_dir = PathManager.get_job_directory(
            config.backend, config.device_name, config.n, config.k, 
            config.trials, config.points, config.shots, config.n_random
        )
        self.history_dir = PathManager.get_history_directory(self.jobs_dir)
        PathManager.ensure_dir(self.jobs_dir)
        if self.history_dir != self.jobs_dir:
            PathManager.ensure_dir(self.history_dir)
            
        self.results_data = []

    def run(self):
        print(f"\n--- QPA Simulation Config ---")
        print(f"Backend: {self.config.backend} ({self.config.device_name})")
        print(f"Method:  {self.config.method}")
        print(f"Topology: N={self.config.n}, K={self.config.k}, Trials={self.config.trials}")
        print(f"Noise: [{self.config.lambda_min}, {self.config.lambda_max}] ({self.config.points} points)")
        print(f"Twirling: {self.config.n_random} instances")
        
        lambdas = np.linspace(self.config.lambda_min, self.config.lambda_max, self.config.points)
        
        # SLURM Array Logic
        if self.config.slurm_task_id is not None:
            if self.config.slurm_task_id < 0 or self.config.slurm_task_id >= len(lambdas):
                print(f"Error: SLURM task ID {self.config.slurm_task_id} is out of range.")
                sys.exit(1)
            print(f"SLURM Array Mode: Processing task {self.config.slurm_task_id}")
            lambdas = [lambdas[self.config.slurm_task_id]]
            base, ext = os.path.splitext(self.config.output)
            self.config.output = f"{base}_task{self.config.slurm_task_id}{ext}"

        # Ensure output directory exists
        output_dir = os.path.dirname(self.config.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Execution Mode
        if self.config.backend in ['aer', 'fake'] and self.config.slurm_task_id is None:
            self.run_parallel(lambdas)
        else:
            self.run_sequential(lambdas)
            
        # Save to CSV
        if not self.config.dry_run and not self.config.post_only:
            self.results_data.sort(key=lambda x: x['lambda'])
            df = pd.DataFrame(self.results_data)
            df.to_csv(self.config.output, index=False)
            print(f"\nResults saved to {self.config.output}")

    def run_parallel(self, lambdas):
        print("\n--- Starting Parallel Execution ---")
        try:
            max_workers = len(os.sched_getaffinity(0))
        except AttributeError:
            max_workers = os.cpu_count() or 1
        
        max_workers = min(max_workers, len(lambdas))
        print(f"Using {max_workers} parallel workers.")
        
        # Disable nested parallelism for workers (Qiskit/Rayon/OMP)
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["RAYON_NUM_THREADS"] = "1"
        os.environ["QISKIT_AER_PARALLEL"] = "False"
        
        # Use spawn context to avoid Qiskit/Rayon issues
        ctx = mp.get_context('spawn')
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            tasks = [(eps, self.config, self.jobs_dir, self.history_dir) for eps in lambdas]
            future_to_eps = {executor.submit(run_simulation_point_wrapper, task): task[0] for task in tasks}
            
            for future in tqdm(concurrent.futures.as_completed(future_to_eps), total=len(lambdas)):
                eps = future_to_eps[future]
                try:
                    result = future.result()
                    if result:
                        final_fid = result['fidelity']
                        print(f"Lambda={eps:.4f} -> Fidelity={final_fid:.4f}")
                        self.results_data.append({'lambda': eps, 'fidelity': final_fid})
                        
                        # Write job history records
                        if result['records']:
                            record_file = os.path.join(self.history_dir, "job_history.jsonl")
                            with open(record_file, "a") as f:
                                for rec in result['records']:
                                    if self.history_dir != self.jobs_dir:
                                        try:
                                            rel_path = os.path.relpath(self.jobs_dir, self.history_dir)
                                            rec['subdir'] = rel_path
                                        except:
                                            pass
                                    f.write(json.dumps(rec) + "\n")
                except Exception as exc:
                    print(f"Lambda={eps:.4f} generated an exception: {exc}")
                    import traceback
                    traceback.print_exc()

    def run_sequential(self, lambdas):
        # ... (Same as before)
        print("\n--- Starting Sequential Execution ---")
        
        # Initialize Backend
        if self.config.backend == 'aer':
            backend_handler = AERHandler()
            if self.config.method == 'dynamic':
                noise_cls = StandardDepolarizingStrategy
                is_dynamic = True
            else:
                noise_cls = PauliTwirlingStrategy
                is_dynamic = False
        elif self.config.backend == 'fake':
            backend_handler = FakeBackendHandler(self.config.device)
            noise_cls = PauliTwirlingStrategy
            is_dynamic = False
        else: # ibm
            backend_handler = IBMRuntimeHandler(backend_name=self.config.device)
            noise_cls = PauliTwirlingStrategy
            is_dynamic = False

        job_service = JobService(backend_handler, output_dir=self.jobs_dir, history_dir=self.history_dir)
        strategy = CircuitFactory.create_strategy(self.config.method, self.config.k, self.config.trials, self.config.n)
        result_processor = ResultProcessor(self.config.k)
        
        # Optimization: Fast Path for Unrolled + PauliTwirling
        use_fast_path = (self.config.method == 'unrolled' and self.config.backend in ['ibm', 'fake', 'aer'] and noise_cls == PauliTwirlingStrategy)
        
        transpiled_golden_circuits = []
        golden_metadata = []
        
        if use_fast_path:
            print("\n--- Pre-Transpiling Golden Circuits (Optimization) ---")
            strategy.set_noise_strategy(None)
            golden_data = strategy.build(0.0)
            golden_circuits = [item['circuit'] for item in golden_data]
            golden_metadata = [{k:v for k,v in item.items() if k!='circuit'} for item in golden_data]
            
            # Use temp TranspilerService for golden
            golden_backend = job_service.sampler.backend if hasattr(job_service.sampler, 'backend') and not callable(job_service.sampler.backend) else backend_handler.get_backend()
            ts = TranspilerService(golden_backend, optimization_level=3)
            transpiled_golden_circuits = ts.transpile(golden_circuits)
            if not isinstance(transpiled_golden_circuits, list):
                transpiled_golden_circuits = [transpiled_golden_circuits]
            print("Golden circuits transpiled.")

        # Batch Execution Context (Post-Only)
        use_batch_context = (self.config.backend == 'ibm' and self.config.post_only)
        
        def run_loop():
            # Create a reusable TranspilerService for the loop
            # Ensure we pass the backend object, not a method
            loop_backend = job_service.sampler.backend if hasattr(job_service.sampler, 'backend') and not callable(job_service.sampler.backend) else backend_handler.get_backend()
            loop_transpiler = TranspilerService(loop_backend)

            for epsilon in tqdm(lambdas):
                total_instances = self.config.n_random if not is_dynamic else 1
                shots_per_circuit = max(1, self.config.shots // total_instances)
                
                if self.config.batch_size == -1:
                    BATCH_SIZE = total_instances
                else:
                    BATCH_SIZE = self.config.batch_size if self.config.batch_size > 0 else 50
                    
                global_path_stats = defaultdict(lambda: {'success': 0, 'total': 0})
                global_dynamic_stats = {'success': 0, 'total': 0}
                num_batches = (total_instances + BATCH_SIZE - 1) // BATCH_SIZE
                
                for batch_idx in range(num_batches):
                    current_batch_size = min(BATCH_SIZE, total_instances - batch_idx * BATCH_SIZE)
                    
                    batch_circuits = []
                    batch_metadata = []
                    
                    if use_fast_path:
                        # Fast Path Logic
                        for _ in range(current_batch_size):
                            noise_strategy = noise_cls(self.config.k)
                            for i, qc_transpiled in enumerate(transpiled_golden_circuits):
                                qc_instance = qc_transpiled.copy()
                                # Need original qc to know registers for noise ops
                                orig_qc = golden_circuits[i]
                                # Assuming Register names start with R...
                                data_regs = [reg for reg in orig_qc.qregs if reg.name.startswith("R")]
                                noise_ops = noise_strategy.generate_noise_ops(data_regs, epsilon)
                                
                                # Apply noise ops to transpiled circuit
                                layout = qc_transpiled.layout.initial_layout if qc_transpiled.layout else None
                                
                                for gate, logical_qubit in noise_ops:
                                    target_qubit = None
                                    if layout and logical_qubit in layout:
                                        phys_qubit_idx = layout[logical_qubit]
                                        target_qubit = qc_instance.qubits[phys_qubit_idx]
                                    elif logical_qubit in qc_instance.qubits:
                                        target_qubit = logical_qubit
                                    else:
                                        # Fallback search
                                        for q in qc_instance.qubits:
                                            # Try matching by register name and index
                                            # This is tricky if registers were flattened.
                                            # But usually Qiskit preserves registers unless flattened.
                                            if hasattr(q, 'register') and hasattr(logical_qubit, 'register'):
                                                 if q.register.name == logical_qubit.register.name and q.index == logical_qubit.index:
                                                     target_qubit = q
                                                     break
                                            # Access private attrs if needed (older qiskit versions)
                                            elif hasattr(q, '_register') and hasattr(logical_qubit, '_register'):
                                                if q._register.name == logical_qubit._register.name and q._index == logical_qubit._index:
                                                    target_qubit = q
                                                    break
                                    
                                    if target_qubit:
                                        # Insert gate at beginning
                                        if self.config.backend in ['ibm', 'fake']:
                                            # Convert Pauli to ISA-safe gates if needed (RZ(pi) for Z, etc)
                                            if gate.name == 'z':
                                                qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                            elif gate.name == 'y':
                                                qc_instance.data.insert(0, CircuitInstruction(RZGate(np.pi), (target_qubit,), ()))
                                                qc_instance.data.insert(0, CircuitInstruction(XGate(), (target_qubit,), ()))
                                            else:
                                                qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                                        else:
                                            qc_instance.data.insert(0, CircuitInstruction(gate, (target_qubit,), ()))
                                
                                batch_circuits.append(qc_instance)
                                batch_metadata.append(golden_metadata[i])
                        
                        transpiled_batch = batch_circuits # Already transpiled
                        
                    else:
                        # Slow Path
                        for _ in range(current_batch_size):
                            noise_strategy = noise_cls(self.config.k)
                            strategy.set_noise_strategy(noise_strategy)
                            circuits_data = strategy.build(epsilon)
                            for item in circuits_data:
                                batch_circuits.append(item['circuit'])
                                batch_metadata.append(item)
                        
                        transpiled_batch = loop_transpiler.transpile(batch_circuits)

                    # Submit
                    try:
                        job_info = job_service.submit_batch(
                            transpiled_batch,
                            shots=shots_per_circuit,
                            job_tags=[f"n{self.config.n}", f"k{self.config.k}", f"lam{epsilon:.4f}", f"batch{batch_idx}"],
                            metadata={
                                'epsilon': epsilon, 
                                'batch_idx': batch_idx,
                                'total_instances': total_instances,
                                'shots_per_circuit': shots_per_circuit,
                                'n_registers': self.config.n,
                                'k': self.config.k,
                                'method': self.config.method
                            },
                            dry_run=self.config.dry_run,
                            save_history=True
                        )
                        
                        if not self.config.dry_run:
                            job_id = job_info['job_id']
                            job_service.save_circuit_metadata(job_id, batch_metadata)
                            
                        # Special handling for local backends: save results even in post-only mode
                        extracted_counts = None
                        if self.config.backend in ['aer', 'fake'] and not self.config.dry_run:
                            job = job_info['job_object']
                            pub_result = job.result()
                            extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                            job_service.save_local_results(job_info['job_id'], extracted_counts)

                        if self.config.dry_run or self.config.post_only:
                            continue

                        # Process Results
                        if extracted_counts is None:
                            job = job_info['job_object']
                            pub_result = job.result()
                            extracted_counts = ResultProcessor.extract_counts_from_job_result(pub_result, is_dynamic=is_dynamic)
                            
                            # Save local results for simulator
                            if self.config.backend in ['aer', 'fake']:
                                job_service.save_local_results(job_info['job_id'], extracted_counts)

                        total_clbits_list = []
                        for counts in extracted_counts:
                            if counts:
                                first_key = next(iter(counts))
                                total_clbits_list.append(len(first_key.replace(" ", "")))
                            else:
                                total_clbits_list.append(0)

                        if not is_dynamic:
                            batch_stats = result_processor.aggregate_batch_stats(extracted_counts, batch_metadata, total_clbits_list)
                            for cond_key, stats in batch_stats.items():
                                global_path_stats[cond_key]['success'] += stats['success']
                                global_path_stats[cond_key]['total'] += stats['total']
                        else:
                            fid = result_processor.process_dynamic_result(extracted_counts[0], total_clbits_list[0])
                            total = sum(extracted_counts[0].values())
                            succ = int(fid * total + 0.5)
                            global_dynamic_stats['success'] += succ
                            global_dynamic_stats['total'] += total
                            
                    except Exception as e:
                        print(f"Error processing batch {batch_idx}: {e}")
                        import traceback
                        traceback.print_exc()

                if not (self.config.dry_run or self.config.post_only):
                    final_fid = 0.0
                    if not is_dynamic:
                        for stats in global_path_stats.values():
                             if stats['total'] > 0:
                                 final_fid += stats['success'] / stats['total']
                    else:
                        if global_dynamic_stats['total'] > 0:
                            final_fid = global_dynamic_stats['success'] / global_dynamic_stats['total']

                    print(f"Lambda={epsilon:.4f} -> Fidelity={final_fid:.4f}")
                    self.results_data.append({'lambda': epsilon, 'fidelity': final_fid})
                    sys.stdout.flush()

        if use_batch_context:
            print("\n--- Running in IBM Batch Mode (Post-Only) ---")
            try:
                with backend_handler.open_batch() as batch:
                    # Update sampler in job_service
                    batch_sampler = backend_handler.get_sampler(backend=batch)
                    job_service.sampler = batch_sampler
                    run_loop()
            except Exception as e:
                print(f"Error during Batch execution: {e}")
        else:
            run_loop()
