import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.primitives import PrimitiveResult
from execution.backend_handler import BackendHandler
from analysis.result_processor import ResultProcessor

class JobManager:
    """
    Manages job submission, tracking, and result retrieval.
    
    This class handles the lifecycle of a job: from transpilation and submission 
    to tracking history and retrieving results.
    """
    def __init__(self, backend_handler: BackendHandler, output_dir: str = "data/jobs", history_dir: Optional[str] = None):
        """
        Args:
            backend_handler (BackendHandler): The handler for the target backend.
            output_dir (str): Directory to save job results and metadata.
            history_dir (str, optional): Directory to save job history logs. If None, uses output_dir.
        """
        self.handler = backend_handler
        self.output_dir = output_dir
        self.history_dir = history_dir if history_dir else output_dir
        self.backend = self.handler.get_backend()
        self.sampler = self.handler.get_sampler(self.backend)
        os.makedirs(self.output_dir, exist_ok=True)
        if self.history_dir != self.output_dir:
            os.makedirs(self.history_dir, exist_ok=True)

    def submit_batch(self, 
                     circuits: List[QuantumCircuit], 
                     shots: int = 1024, 
                     job_tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     dry_run: bool = False,
                     optimization_level: Optional[int] = None,
                     skip_transpilation: bool = False) -> Dict[str, Any]:
        """
        Submits a batch of circuits to the backend.
        
        Args:
            circuits (List[QuantumCircuit]): List of QuantumCircuits to run.
            shots (int): Number of shots per circuit.
            job_tags (List[str], optional): Tags for the job (e.g., ['project:QPA', 'experiment:test']).
            metadata (Dict[str, Any], optional): Extra info to save with the job ID record.
            dry_run (bool): If True, transpiles but does not submit.
            optimization_level (int, optional): Explicit transpilation level. If None, auto-selects.
            skip_transpilation (bool): If True, skips transpilation and submits circuits as-is.
            
        Returns:
            Dict[str, Any]: A dictionary containing 'job_id', 'status', and optionally 'job_object'.
        """
        print(f"preparing to submit {len(circuits)} circuits...")
        
        if skip_transpilation:
            print("Skipping transpilation (assuming circuits are ISA compliant)...")
            transpiled_circuits = circuits
        
        if not skip_transpilation:
            # Note: SamplerV2 often handles transpilation, but explicit transpilation 
            # gives us more control and ensures compatibility before submission.
            # Determine if it is a simulator
            backend_type = str(type(self.backend)).lower()
            is_sim = "aer" in backend_type or "fake" in backend_type

            # Determine optimization level
            if optimization_level is not None:
                opt_level = optimization_level
            else:
                # Use optimization_level=1 for Aer and Fake backends to speed up transpilation
                opt_level = 3 if not is_sim else 1
            
            # Check if circuits are already ISA circuits (transpiled)
            print(f"Transpiling with optimization_level={opt_level}...")
            
            # Use parallel transpilation via the 'num_processes' argument available in transpile()
            # We must respect the SLURM allocation to avoid OOM from spawning too many processes.
            # os.cpu_count() returns total physical cores, which is dangerous in shared environments.
            try:
                # Linux specific: gets the set of CPUs the process is allowed to run on
                num_cores = len(os.sched_getaffinity(0))
            except AttributeError:
                # Fallback for non-Linux or if method missing
                num_cores = os.cpu_count() or 1
                
            print(f"Using {num_cores} cores for parallel transpilation.")
            
            transpiled_circuits = transpile(
                circuits, 
                backend=self.backend, 
                optimization_level=opt_level,
                num_processes=num_cores
            )
        else:
             # Determine if it is a simulator (needed for logic below)
             backend_type = str(type(self.backend)).lower()
             is_sim = "aer" in backend_type or "fake" in backend_type
        
        if dry_run:
            print("Dry run: Skipping submission.")
            return {"job_id": "dry_run", "status": "simulated"}

        # 2. Run
        # SamplerV2.run() takes a list of (circuit, parameter_values) or just circuits.
        # It accepts 'shots' in the run options.
        try:
            # Note: The API for shots depends on the exact Sampler version.
            # Qiskit Runtime SamplerV2: run([pubs], shots=...) is not standard.
            # Usually run([ (qc, None, shots) ]) or run(..., options={'shots': shots})
            # Let's try the standard V2 pub format: (circuit, data, shots)
            
            pubs = [(qc, None, shots) for qc in transpiled_circuits]
            
            print("Submitting job...")
            job = self.sampler.run(pubs)
            job_id = job.job_id()
            print(f"Job submitted! ID: {job_id}")
            
            # 3. Save Record
            # Determine the directory for job_history.jsonl
            # The main.py passes output_dir which is .../timestamp/
            # We want job_history to be in .../pXX/ (two levels up from timestamp, or one level up from config)
            # Structure: .../pXX/sXX_cXX/timestamp/
            # job_history.jsonl should be in .../pXX/job_history.jsonl
            
            # Try to find the pXX directory
            # This logic is a bit brittle if the path structure changes, but for now:
            # self.output_dir is .../pXX/sXX_cXX/timestamp
            
            self._save_job_record(job_id, job_tags, metadata, self.history_dir)
            
            # Special handling for local backends (Aer/Fake):
            # Save the results to disk immediately so they can be "retrieved" later.
            # Even in post-only mode, we execute the simulation locally and save the results.
            if is_sim:
                try:
                    result = job.result()
                    
                    # Determine method (dynamic/unrolled) from metadata
                    method = metadata.get('method', 'unrolled') if metadata else 'unrolled'
                    is_dynamic = (method == 'dynamic')
                    
                    # Extract counts using ResultProcessor
                    extracted_counts = ResultProcessor.extract_counts_from_job_result(result, is_dynamic=is_dynamic)
                    
                    # Save to JSON
                    result_path = os.path.join(self.output_dir, f"{job_id}_result.json")
                    with open(result_path, 'w') as f:
                        json.dump(extracted_counts, f)
                    print(f"Local job results saved to {result_path}")
                    
                except Exception as e:
                    print(f"Warning: Failed to save local job results: {e}")
            
            return {"job_id": job_id, "job_object": job}
            
        except Exception as e:
            print(f"Error submitting job: {e}")
            raise e

    def retrieve_result(self, job_id: str) -> PrimitiveResult:
        """
        Retrieves results for a given job ID. 
        
        Args:
            job_id (str): The Job ID string.

        Returns:
            PrimitiveResult: The result object from the backend.

        Raises:
            NotImplementedError: If the backend does not support retrieval by ID (e.g., local Aer).
        """
        # This requires the service to retrieve the job. 
        # The current Sampler abstraction might not expose retrieve_job easily 
        # unless we go through the service.
        # For now, we assume we have the job object from submit_batch in the same session,
        # or we re-initialize the service.
        
        # If it's IBM Runtime, we can fetch the job.
        if hasattr(self.handler, '_get_service'):
            service = self.handler._get_service()
            job = service.job(job_id)
            return job.result()
        else:
            raise NotImplementedError("Job retrieval by ID is only supported for IBM Runtime backends currently.")

    def _save_job_record(self, job_id: str, tags: List[str], metadata: Dict[str, Any], history_dir: str = None):
        """Helper to save job details to a local JSONL file."""
        record = {
            "job_id": job_id,
            "timestamp": pd.Timestamp.now().isoformat(),
            "tags": tags or [],
            "metadata": metadata or {}
        }
        
        if history_dir is None:
            history_dir = self.output_dir
            
        # Calculate relative path (subdir) if history_dir is different from output_dir
        if history_dir != self.output_dir:
            try:
                # Assuming output_dir is a subdirectory of history_dir or related
                rel_path = os.path.relpath(self.output_dir, history_dir)
                record['subdir'] = rel_path
            except ValueError:
                pass
            
        # Append to a JSONL file
        record_file = os.path.join(history_dir, "job_history.jsonl")
        with open(record_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        print(f"Job record saved to {record_file}")
