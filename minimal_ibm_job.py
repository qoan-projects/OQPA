import argparse
import os
import sys
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from itertools import product
from dataclasses import dataclass
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Qiskit Imports
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.circuit import Parameter, CircuitInstruction
from qiskit.circuit.library import IGate, XGate, YGate, ZGate, RZGate, RXGate
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as IBMSampler

# Load environment variables
load_dotenv()

# ==========================================
# 1. Helper Functions (Ops)
# ==========================================

def apply_schur_test(qc: QuantumCircuit, ancilla, reg_a, reg_b, k: int):
    """Performs a Schur test (swap test) between two registers controlled by an ancilla."""
    qc.h(ancilla)
    for i in range(k):
        # qc.cswap(ancilla, reg_a[i], reg_b[i])
        # Note: reg_a[i] might be a Qubit object or index depending on usage.
        # Assuming Qubit objects here.
        qc.cswap(ancilla, reg_a[i], reg_b[i])
    qc.h(ancilla)

def apply_cyclic_rotation_indices(qc: QuantumCircuit, indices: list, k: int):
    """
    Applies physical SWAP gates to rotate data among the specified register indices.
    Rotates: indices[0] -> indices[-1], indices[1] -> indices[0], etc. (Left Rotation)
    """
    # qc.qubits assumes data registers are the first N*k qubits in the circuit.
    # We assume registers R1...Rn are added first.
    
    for i in range(len(indices)-1, 0, -1):
        idx_j = indices[i]
        idx_j_minus_1 = indices[i-1]
        
        # Swap full registers
        for b in range(k):
            # Calculate physical qubit indices
            # Assumes registers are contiguous and start at 0
            q_j = qc.qubits[idx_j*k + b]
            q_j_1 = qc.qubits[idx_j_minus_1*k + b]
            qc.swap(q_j, q_j_1)

# ==========================================
# 2. Register Management
# ==========================================

class QPARegisters:
    """Manages the quantum and classical registers for the QPA protocol."""
    def __init__(self, n_registers: int, k: int, n_trials: int, use_ancilla_pool: bool = False, no_reset: bool = False):
        self.n = n_registers
        self.k = k
        self.n_trials = n_trials
        self.no_reset = no_reset
        
        # Data Registers (R1...Rn)
        self.qr_data = [QuantumRegister(k, f"R{i+1}") for i in range(n_registers)]
        
        self.qr_ancilla = []
        self.cr_ancilla = None
        self.cr_readout = ClassicalRegister(k, "readout")
        self.use_ancilla_pool = use_ancilla_pool
        
        if use_ancilla_pool:
            # Unrolled Strategy Logic
            num_concurrent_tests = n_registers // 2
            
            if no_reset:
                total_ancillas = num_concurrent_tests * n_trials
                self.qr_ancilla = [QuantumRegister(1, f"anc_{i}") for i in range(total_ancillas)]
            else:
                self.qr_ancilla = [QuantumRegister(1, f"anc_{i}") for i in range(num_concurrent_tests)]
                
            max_total_measurements = n_trials * (n_registers // 2)
            self.cr_ancilla = ClassicalRegister(max_total_measurements, "anc_meas")

    def get_circuit_registers(self) -> List:
        regs = [*self.qr_data]
        if self.use_ancilla_pool:
            regs.extend(self.qr_ancilla)
            regs.append(self.cr_readout)
            regs.append(self.cr_ancilla)
        return regs

# ==========================================
# 3. Noise & Strategy Classes
# ==========================================

class NoiseStrategy(ABC):
    @abstractmethod
    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        pass

    def generate_bindings(self, circuit: QuantumCircuit, num_randomizations: int, epsilon: float) -> np.ndarray:
        return np.empty((num_randomizations, 0))

class ParameterizedPauliTwirlingStrategy(NoiseStrategy):
    """Applies parameterized rotations to simulate Pauli Twirling."""
    def __init__(self, k: int):
        self.k = k

    def apply_noise(self, qc: QuantumCircuit, registers: List[QuantumRegister], epsilon: float):
        current_param_count = len(qc.parameters)
        
        for reg in registers:
            register_uid = current_param_count
            current_param_count += 2 * len(reg)
            
            for i, q in enumerate(reg):
                px_name = f"twirl_{register_uid}_q{i}_x"
                pz_name = f"twirl_{register_uid}_q{i}_z"
                
                theta_x = Parameter(px_name)
                theta_z = Parameter(pz_name)
                
                qc.append(RZGate(theta_z), [q])
                qc.append(RXGate(theta_x), [q])

    def generate_bindings(self, circuit: QuantumCircuit, num_randomizations: int, epsilon: float) -> np.ndarray:
        rng = np.random.default_rng()
        circuit_params = circuit.parameters
        num_params = len(circuit_params)
        
        if num_params == 0:
            return np.empty((num_randomizations, 0))
            
        bindings_matrix = np.zeros((num_randomizations, num_params))
        reg_map = {}
        
        # Map params to registers
        for i, param in enumerate(circuit_params):
            name = param.name
            if name.startswith("twirl_"):
                parts = name.split('_')
                if len(parts) >= 4:
                    r_uid = int(parts[1])
                    q_idx = int(parts[2][1:])
                    p_type = parts[3]
                    
                    if r_uid not in reg_map: reg_map[r_uid] = {}
                    if q_idx not in reg_map[r_uid]: reg_map[r_uid][q_idx] = {}
                    reg_map[r_uid][q_idx][p_type] = i
        
        vals_x = [0.0, np.pi, 0.0, np.pi]
        vals_z = [0.0, 0.0, np.pi, np.pi]
        
        for r_uid, qubits_map in reg_map.items():
            k = len(qubits_map)
            num_paulis = 4**k
            
            is_error = rng.random(size=num_randomizations) < epsilon
            error_indices = rng.integers(0, num_paulis, size=num_randomizations)
            final_indices = np.where(is_error, error_indices, 0)
            
            sorted_q_indices = sorted(qubits_map.keys())
            current_val = final_indices
            
            for q_idx in sorted_q_indices:
                p_choice = current_val % 4
                current_val = current_val // 4
                
                p_indices = qubits_map[q_idx]
                if 'x' in p_indices:
                    bx = np.array([vals_x[c] for c in p_choice])
                    bindings_matrix[:, p_indices['x']] = bx
                if 'z' in p_indices:
                    bz = np.array([vals_z[c] for c in p_choice])
                    bindings_matrix[:, p_indices['z']] = bz
                    
        return bindings_matrix

class CircuitGenerationStrategy(ABC):
    def __init__(self, k: int, n_trials: int, n_registers: int):
        self.k = k
        self.n_trials = n_trials
        self.n_registers = n_registers
        self.noise_strategy: Optional[NoiseStrategy] = None

    def set_noise_strategy(self, strategy: NoiseStrategy):
        self.noise_strategy = strategy

    @abstractmethod
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        pass

class UnrolledStrategy(CircuitGenerationStrategy):
    """Builds a set of static circuits representing all execution paths."""
    def __init__(self, k: int, n_trials: int, n_registers: int, no_reset: bool = False):
        super().__init__(k, n_trials, n_registers)
        self.no_reset = no_reset
        self.circuits_data = []

    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        self.circuits_data = []
        regs = QPARegisters(self.n_registers, self.k, self.n_trials, use_ancilla_pool=True, no_reset=self.no_reset)
        qc_template = QuantumCircuit(*regs.get_circuit_registers())
        
        if self.noise_strategy:
            self.noise_strategy.apply_noise(qc_template, regs.qr_data, epsilon)

        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append([i, i+1])
        reserve = self.n_registers - 1
        
        self._recurse(qc_template, initial_pairs, reserve, trial=0, 
                      conditions={}, total_meas_index=0, regs=regs)
        
        return self.circuits_data

    def _recurse(self, current_qc: QuantumCircuit, current_pairs: List[List[int]], 
                 reserve_idx: int, trial: int, conditions: dict, total_meas_index: int, regs: QPARegisters):
        
        if trial >= self.n_trials:
            self._finalize_path(current_qc, conditions, reserve_idx, regs)
            return

        num_pairs = len(current_pairs)
        outcomes = list(product([0, 1], repeat=num_pairs))
        
        for outcome in outcomes:
            branch_qc = current_qc.copy()
            branch_conditions = conditions.copy()
            
            for i, pair in enumerate(current_pairs):
                if self.no_reset:
                    num_concurrent = self.n_registers // 2
                    anc_idx = trial * num_concurrent + i
                    anc_qubit = regs.qr_ancilla[anc_idx]
                else:
                    anc_qubit = regs.qr_ancilla[i]
                
                rA_idx, rB_idx = pair
                rA = branch_qc.qubits[rA_idx*self.k : (rA_idx+1)*self.k]
                rB = branch_qc.qubits[rB_idx*self.k : (rB_idx+1)*self.k]
                
                apply_schur_test(branch_qc, anc_qubit, rA, rB, self.k)
                
                cl_idx = total_meas_index + i
                branch_qc.measure(anc_qubit, regs.cr_ancilla[cl_idx])
                
                if not self.no_reset:
                    branch_qc.reset(anc_qubit)
                
                branch_conditions[self.k + cl_idx] = outcome[i]

            surviving_pairs = []
            for i, res in enumerate(outcome):
                if res == 0: surviving_pairs.append(current_pairs[i])
            
            num_survivors = len(surviving_pairs)

            if num_survivors >= 1:
                survivor_flat = [idx for p in surviving_pairs for idx in p]
                active_indices = survivor_flat + [reserve_idx]
                
                apply_cyclic_rotation_indices(branch_qc, active_indices, self.k)
                
                new_active = active_indices 
                new_pairs = []
                for i in range(0, len(new_active) - 1, 2):
                    new_pairs.append([new_active[i], new_active[i+1]])
                new_reserve = new_active[-1]
                
                self._recurse(branch_qc, new_pairs, new_reserve, trial + 1, 
                              branch_conditions, total_meas_index + num_pairs, regs)
            else:
                self._finalize_path(branch_qc, branch_conditions, reserve_idx, regs)

    def _finalize_path(self, qc, conditions, reserve_idx, regs):
        final_qc = qc.copy()
        for i in range(self.k):
            r_qubits = final_qc.qubits[reserve_idx*self.k : (reserve_idx+1)*self.k]
            final_qc.measure(r_qubits[i], regs.cr_readout[i]) 
        
        self.circuits_data.append({
            'circuit': final_qc,
            'conditions': conditions,
            'metadata': {'type': 'unrolled', 'path_name': f"path_{len(self.circuits_data)}"}
        })

# ==========================================
# 4. IBM Execution Handlers
# ==========================================

class IBMRuntimeHandler:
    def __init__(self, backend_name: str, channel: str = "ibm_quantum"):
        self.backend_name = backend_name
        self.token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBM_API")
        self._service = None
        self.channel = channel

    def _get_service(self):
        if self._service is None:
            print(f"Connecting to IBM Runtime ({self.channel})...")
            try:
                self._service = QiskitRuntimeService(channel=self.channel, token=self.token)
            except Exception as e:
                print(f"Connection failed: {e}")
                sys.exit(1)
        return self._service

    def get_backend(self):
        return self._get_service().backend(self.backend_name)

    def get_sampler(self, backend=None) -> IBMSampler:
        if backend is None: backend = self.get_backend()
        return IBMSampler(mode=backend)

class TranspilerService:
    def __init__(self, backend, optimization_level: int = 3):
        self.backend = backend
        self.optimization_level = optimization_level

    def transpile(self, circuits: List[QuantumCircuit]) -> List[QuantumCircuit]:
        print(f"Transpiling {len(circuits)} circuits (Opt Level {self.optimization_level})...")
        return transpile(circuits, backend=self.backend, optimization_level=self.optimization_level)

class JobService:
    def __init__(self, backend_handler: IBMRuntimeHandler, output_dir: str):
        self.handler = backend_handler
        self.sampler = self.handler.get_sampler()
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def submit_pubs(self, pubs: List[Tuple[QuantumCircuit, Any, int]], 
                    job_tags: List[str], metadata: List[Dict], dry_run: bool = False):
        if dry_run:
            print("[Dry Run] Would submit job with tags:", job_tags)
            return {"job_id": "dry_run"}
            
        print(f"Submitting job with {len(pubs)} PUBs...")
        try:
            job = self.sampler.run(pubs)
            job_id = job.job_id()
            print(f"Job Submitted! ID: {job_id}")
            self.save_circuit_metadata(job_id, metadata)
            return {"job_id": job_id, "job_object": job}
        except Exception as e:
            print(f"Submission Error: {e}")
            raise e

    def save_circuit_metadata(self, job_id: str, batch_metadata: List[Dict]):
        path = os.path.join(self.output_dir, f"{job_id}_circuit_meta.json")
        # Clean metadata (remove circuit objects)
        clean_meta = [{k: v for k, v in item.items() if k != 'circuit'} for item in batch_metadata]
        with open(path, 'w') as f:
            json.dump(clean_meta, f)
        print(f"Metadata saved to {path}")

# ==========================================
# 5. Main Execution Logic
# ==========================================

def parse_arguments():
    parser = argparse.ArgumentParser(description="Minimal IBM Job Runner (Unrolled + Parameterized)")
    parser.add_argument('--backend', type=str, default='ibm', help="Backend type (ibm)")
    parser.add_argument('--device', type=str, required=True, help="IBM Device Name (e.g. ibm_brisbane)")
    parser.add_argument('--method', type=str, default='parameterized', help="Must be 'parameterized'")
    
    # QPA Params
    parser.add_argument('--n', type=int, default=3, help="Number of registers")
    parser.add_argument('--k', type=int, default=2, help="Qubits per register")
    parser.add_argument('--trials', type=int, default=3, help="Number of trials")
    
    # Noise/Execution
    parser.add_argument('--lambda-val', type=float, default=0.75, help="Noise value (epsilon)")
    parser.add_argument('--shots', type=int, default=16000, help="Total shots")
    parser.add_argument('--n-random', type=int, default=8000, help="Total randomizations")
    parser.add_argument('--batch-size', type=int, default=4000, help="Batch size for bindings")
    
    # Flags
    parser.add_argument('--post-only', action='store_true', help="Submit only, don't wait")
    parser.add_argument('--no-batchmode', action='store_true', help="Disable IBM Batch Mode")
    parser.add_argument('--dry-run', action='store_true', help="Simulate submission")
    parser.add_argument('--output', type=str, default='results.csv', help="Output path")
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    print(f"--- Minimal IBM Job Runner ---")
    print(f"Device: {args.device}")
    print(f"Topology: N={args.n}, K={args.k}, Trials={args.trials}")
    print(f"Epsilon: {args.lambda_val}")
    print(f"Shots: {args.shots}, Randomizations: {args.n_random}, Batch Size: {args.batch_size}")
    
    # 1. Setup Backend
    backend_handler = IBMRuntimeHandler(args.device)
    output_dir = os.path.dirname(args.output) if os.path.dirname(args.output) else "."
    job_service = JobService(backend_handler, output_dir)
    
    # 2. Build Circuits (Structure)
    print("\n--- Building Circuit Structure ---")
    strategy = UnrolledStrategy(args.k, args.trials, args.n)
    noise_strategy = ParameterizedPauliTwirlingStrategy(args.k)
    strategy.set_noise_strategy(noise_strategy)
    
    # Build paths
    circuits_data = strategy.build(args.lambda_val)
    path_circuits = [item['circuit'] for item in circuits_data]
    path_metadata = circuits_data
    print(f"Generated {len(path_circuits)} execution paths.")
    
    # 3. Transpile
    backend = backend_handler.get_backend()
    transpiler = TranspilerService(backend)
    transpiled_paths = transpiler.transpile(path_circuits)
    if not isinstance(transpiled_paths, list): transpiled_paths = [transpiled_paths]
    
    # 4. Generate Bindings & Submit Batches
    total_randomizations = args.n_random
    shots_total = args.shots
    shots_per_binding = max(1, shots_total // total_randomizations)
    
    # Batching Logic
    bindings_batch_size = args.batch_size if args.batch_size > 0 else total_randomizations
    num_jobs = (total_randomizations + bindings_batch_size - 1) // bindings_batch_size
    
    print(f"\n--- Submitting {num_jobs} Jobs ---")
    print(f"Shots per binding: {shots_per_binding}")
    
    for job_idx in range(num_jobs):
        start_idx = job_idx * bindings_batch_size
        end_idx = min(start_idx + bindings_batch_size, total_randomizations)
        current_batch_count = end_idx - start_idx
        
        print(f"Job {job_idx+1}/{num_jobs}: {current_batch_count} bindings")
        
        pubs_payload = []
        job_meta = []
        
        for i, qc in enumerate(transpiled_paths):
            # Generate bindings for this slice
            bindings = noise_strategy.generate_bindings(qc, current_batch_count, args.lambda_val)
            pubs_payload.append((qc, bindings, shots_per_binding))
            
            # Metadata
            meta_copy = {k: v for k, v in path_metadata[i].items() if k != 'circuit'}
            meta_copy.update({
                'epsilon': args.lambda_val,
                'job_idx': job_idx,
                'num_randomizations': current_batch_count,
                'shots_per_binding': shots_per_binding
            })
            job_meta.append(meta_copy)
            
        # Submit
        job_tags = [f"n{args.n}", f"k{args.k}", f"lam{args.lambda_val:.4f}", f"job{job_idx}", "parameterized"]
        job_service.submit_pubs(pubs_payload, job_tags, job_meta, dry_run=args.dry_run)
        
    print("\nAll jobs submitted.")
    if args.post_only:
        print("Post-only mode: Exiting without waiting for results.")

if __name__ == "__main__":
    main()
