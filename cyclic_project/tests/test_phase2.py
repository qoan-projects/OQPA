import sys
import os
import json
import shutil
from qiskit import QuantumCircuit

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from execution.backend_handler import AERHandler, FakeBackendHandler
from execution.job_manager import JobManager

def test_backend_instantiation():
    print("\n--- Testing Backend Instantiation ---")
    aer = AERHandler()
    print(f"AER Backend: {aer.get_backend()}")
    
    # Note: FakeBackend might warn if name unknown, but should return a default
    fake = FakeBackendHandler("fake_sherbrooke")
    try:
        print(f"Fake Backend: {fake.get_backend()}")
    except Exception as e:
        print(f"Fake Backend instantiation failed (expected if missing specific deps): {e}")

def test_job_submission():
    print("\n--- Testing Job Submission (AER) ---")
    
    # Setup
    output_dir = "tests/data/jobs"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    handler = AERHandler()
    manager = JobManager(handler, output_dir=output_dir)
    
    # Create simple circuit
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()
    
    # Submit
    result = manager.submit_batch([qc], shots=100, job_tags=["test_phase2"])
    
    # Verify
    job_id = result["job_id"]
    print(f"Job ID: {job_id}")
    assert job_id is not None
    
    # Check if record file exists
    history_file = os.path.join(output_dir, "job_history.jsonl")
    assert os.path.exists(history_file)
    
    with open(history_file, 'r') as f:
        line = f.readline()
        record = json.loads(line)
        print(f"Saved Record: {record}")
        assert record["job_id"] == job_id
        assert "test_phase2" in record["tags"]

    print("SUCCESS: Job submitted and recorded.")

if __name__ == "__main__":
    test_backend_instantiation()
    test_job_submission()
