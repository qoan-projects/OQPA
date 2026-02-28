import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from qiskit import QuantumCircuit
from execution.backend_handler import BackendHandler

class JobService:
    def __init__(self, backend_handler: BackendHandler, output_dir: str, history_dir: Optional[str] = None):
        self.handler = backend_handler
        self.output_dir = output_dir
        self.history_dir = history_dir if history_dir else output_dir
        self.sampler = self.handler.get_sampler(self.handler.get_backend())
        
        os.makedirs(self.output_dir, exist_ok=True)
        if self.history_dir != self.output_dir:
            os.makedirs(self.history_dir, exist_ok=True)

    def submit_batch(self, 
                     transpiled_circuits: List[QuantumCircuit], 
                     shots: int, 
                     job_tags: List[str],
                     metadata: Dict[str, Any],
                     dry_run: bool = False,
                     save_history: bool = True) -> Dict[str, Any]:
        
        if dry_run:
            return {"job_id": "dry_run", "status": "simulated"}

        try:
            pubs = [(qc, None, shots) for qc in transpiled_circuits]
            
            print(f"Submitting {len(pubs)} circuits...")
            job = self.sampler.run(pubs)
            job_id = job.job_id()
            print(f"Job submitted! ID: {job_id}")
            
            if save_history:
                self._save_job_record(job_id, job_tags, metadata)
                
            return {"job_id": job_id, "job_object": job, "record": self._create_record(job_id, job_tags, metadata)}
            
        except Exception as e:
            print(f"Error submitting job: {e}")
            raise e

    def save_local_results(self, job_id: str, results: Any):
        path = os.path.join(self.output_dir, f"{job_id}_result.json")
        with open(path, 'w') as f:
            json.dump(results, f)
        print(f"Local job results saved to {path}")

    def save_circuit_metadata(self, job_id: str, batch_metadata: List[Dict]):
        path = os.path.join(self.output_dir, f"{job_id}_circuit_meta.json")
        clean_meta = [{k: v for k, v in item.items() if k != 'circuit'} for item in batch_metadata]
        with open(path, 'w') as f:
            json.dump(clean_meta, f)

    def _create_record(self, job_id, tags, metadata):
        return {
            "job_id": job_id,
            "timestamp": pd.Timestamp.now().isoformat(),
            "tags": tags or [],
            "metadata": metadata or {}
        }

    def _save_job_record(self, job_id, tags, metadata):
        record = self._create_record(job_id, tags, metadata)
        
        if self.history_dir != self.output_dir:
            try:
                rel_path = os.path.relpath(self.output_dir, self.history_dir)
                record['subdir'] = rel_path
            except ValueError:
                pass
            
        record_file = os.path.join(self.history_dir, "job_history.jsonl")
        with open(record_file, "a") as f:
            f.write(json.dumps(record) + "\n")
