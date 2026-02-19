import argparse
import os
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class SimulationConfig:
    backend: str
    device: str
    method: str
    n: int
    k: int
    trials: int
    lambda_min: float
    lambda_max: float
    points: int
    n_random: int
    shots: int
    dry_run: bool
    post_only: bool
    output: str
    batch_size: int
    slurm_task_id: Optional[int]
    slurm_num_tasks: Optional[int]
    
    # Derived/Computed fields
    device_name: str = field(init=False)
    
    def __post_init__(self):
        # Determine effective device name (logic moved from main.py)
        if self.backend == 'aer':
            if self.device == 'ibm_brisbane':
                if self.method == 'dynamic':
                    self.device_name = 'aer_dynamic'
                else:
                    self.device_name = 'aer_unrolled'
            else:
                self.device_name = f"{self.device}_{self.method}"
        else:
            self.device_name = self.device

def parse_arguments() -> SimulationConfig:
    parser = argparse.ArgumentParser(description="QPA Modular Simulation")
    parser.add_argument('--backend', type=str, choices=['aer', 'fake', 'ibm'], default='aer', help="Target backend type")
    parser.add_argument('--device', type=str, default='ibm_brisbane', help="Specific device name (for fake/ibm)")
    
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

    return SimulationConfig(
        backend=args.backend,
        device=args.device,
        method=method,
        n=args.n,
        k=args.k,
        trials=args.trials,
        lambda_min=args.lambda_min,
        lambda_max=args.lambda_max,
        points=args.points,
        n_random=args.n_random,
        shots=args.shots,
        dry_run=args.dry_run,
        post_only=args.post_only,
        output=args.output,
        batch_size=args.batch_size,
        slurm_task_id=args.slurm_task_id,
        slurm_num_tasks=args.slurm_num_tasks
    )
