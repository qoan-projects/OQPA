"""
fidelity_comparison.py - Compare QPA circuit fidelity with and without noise

This script compares the fidelity of QPA (Quantum Phase Algorithm) circuits with
and without noise, using either trotterized or exact statevector as the target state.
It generates plots showing how fidelity changes with different noise strengths (epsilon).

Key Features:
- Implements Ising model simulation with trotterized evolution
- Supports both exact and trotterized statevector preparation
- Uses Aer simulator with custom noise models
- Compares fidelity of Ising circuit vs QPA circuit
- Supports configurable noise strength (epsilon) sweeps
- Generates plots comparing fidelity vs noise strength

How to Run:
python fidelity_comparison.py [OPTIONS]

Required Dependencies:
- qiskit
- numpy
- pandas
- matplotlib
- scipy

Example Usage:
1. Basic run with default parameters:
   python fidelity_comparison.py

2. Run with specific parameters:
   python estimation_scripts/fidelity_comparison.py --shots 1024 --t 3.0 --J 1.0 --h 1.0 --steps 5       --eps_min 0.0 --eps_max 0.1 --eps_steps 20 --output output.png --trotter True

3. Run with different noise range:
   python fidelity_comparison.py --eps_min 0.0 --eps_max 0.2 --eps_steps 20

The script will generate:
- A plot comparing Ising vs QPA circuit fidelities
- CSV files containing the raw fidelity data
- Circuit diagrams (if requested)

Note: The script uses Aer simulator with custom noise models that include:
- Depolarizing errors for 1-qubit gates (id_noisy, rx)
- Depolarizing errors for 2-qubit gates (rzz)
- Depolarizing errors for 3-qubit gates (cswap)
- Readout errors
"""

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
import os
import logging
from datetime import datetime
import qiskit.circuit.classical as qiskit_classical
from scipy.linalg import expm
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit.quantum_info import (
    Statevector,
    SparsePauliOp
)
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    depolarizing_error,
)
from qiskit.visualization import circuit_drawer
from qiskit.circuit.library import RZZGate, IGate
class ising_class:
    """
    Class for generating Ising model circuits and statevectors.
    
    Args:
        d: Number of qubits per register
        steps: Number of Trotter steps
        t: Evolution time
        J: Interaction strength
        h: Transverse field strength
    """
    def __init__(self, d, steps, t, J, h):
        self.d = d
        self.steps = steps
        self.t = t
        self.J = J
        self.h = h

    def get_trotterized_ising_circuit(self):
        """
        Returns a QuantumCircuit implementing a trotterized Ising evolution.
        """
        dt = self.t / self.steps
        qc = QuantumCircuit(self.d)

        for _ in range(self.steps):
            # Apply ZZ interactions (Z_i Z_{i+1})
            for i in range(self.d - 1):
                qc.cx(i, i + 1)
                qc.rz(-2 * self.J * dt, i + 1)
                qc.cx(i, i + 1)

            # Apply transverse field X terms (X_i)
            for i in range(self.d):
                qc.rx(-2 * self.h * dt, i)

        return qc

    def apply_ising_to_registers(self, qc,start):
        """
        Apply trotterized Ising circuit to registers q1, q2, q3 in a 4d-sized register circuit.
        """
        ising = self.get_trotterized_ising_circuit()
        for reg in [1, 2, 3]:
            for gate, qargs, cargs in ising.data:
                mapped_qargs = [qc.qubits[start+(reg-1) * self.d + ising.qubits.index(q)] for q in qargs]
                qc.append(gate, mapped_qargs, cargs)
        return qc

    def get_trotterized_ising_statevector(self):
        """
        Returns the statevector from the trotterized Ising evolution.
        """
        qc = self.get_trotterized_ising_circuit()
        qc.save_statevector()
        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def get_QPA_circuit(d, ising_circuit, nqpa):
    """
    Returns a simplified QPA circuit with single control qubit and single QPA sequence.
    
    Args:
        d: Number of qubits per register
        ising_circuit: ising_class instance
        
    Returns:
        QuantumCircuit implementing the QPA sequence
    """
    # Single control qubit
    cr = ClassicalRegister(1, name='control')
    qr_all = QuantumRegister(3*d + 1)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)
    
    # Apply Ising circuit to registers
    qc = ising_circuit.apply_ising_to_registers(qc, start=1)
    if nqpa==0:
        return qc

    assert nqpa==1 #Cannot have a different value for this circuit for now
    
    # Single QPA sequence
    qc.h(0)      # Apply Hadamard
    for k in range(d):
        qc.cswap(0, k+1, k+d+1)  # Control qubit 0, target q1 and q2
    qc.h(0)      # Apply second Hadamard
    
    return qc
def get_original_QPA_circuit(k, ising_circuit, N):
    cr_q0 = ClassicalRegister(k, name='control')
    qr_all = QuantumRegister(4 * k)
    qcSWAP = QuantumCircuit(qr_all, cr_q0)
    qc = ising_circuit.apply_ising_to_registers(qcSWAP,start=k)

    def recursive(N, qc):
        for i in range(k):
            qc.reset(i)
        qc.h(0)
        for i in range(k - 1):
            qc.cx(0, 1 + i)
        for i in range(k):
            qc.append(IGate(label='id_noisy'), [i])
            qc.cswap(0 + i, i + k, i + 2 * k)
        for i in range(k):
            qc.h(i)
        for i in range(k):
            qc.measure(i, cr_q0[i])
            if i == 0:
                parity_control = qiskit_classical.expr.lift(cr_q0[i])
            else:
                parity_control = qiskit_classical.expr.bit_xor(parity_control, cr_q0[i])
        with qc.if_test(parity_control) as _else:
            pass
        with _else:
            for i in range(k):
                qc.swap(i + 2 * k, i + 3 * k)
            if N != 1:
                qc = recursive(N - 1, qc)
        return qc

    if N != 0:
        qc = recursive(N, qcSWAP)
    else:
        qc = qcSWAP
    return qc
def compute_exact_statevector(k, t, J, h):
    """
    Compute the exact statevector for the Ising Hamiltonian.
    
    Args:
        k: Number of qubits
        t: Evolution time
        J: Interaction strength
        h: Transverse field strength
        
    Returns:
        Statevector of the evolved state
    """
    dim = 2**k
    I = np.eye(2)
    X = np.array([[0, 1], [1, 0]])
    Z = np.array([[1, 0], [0, -1]])

    def kron_n(*ops):
        """Kronecker product of operators."""
        out = ops[0]
        for op in ops[1:]:
            out = np.kron(out, op)
        return out

    # Build Hamiltonian
    H = np.zeros((dim, dim), dtype=complex)
    for q in range(k - 1):
        ops = [I] * k
        ops[q] = Z
        ops[q + 1] = Z
        H += -J * kron_n(*ops)
    
    for q in range(k):
        ops = [I] * k
        ops[q] = X
        H += -h * kron_n(*ops)

    # Initial state |000>
    psi0 = np.zeros(dim, dtype=complex)
    psi0[0] = 1.0

    # Time evolution: U = exp(-iHt)
    U = expm(-1j * H * t)
    psi_final = U @ psi0

    return Statevector(psi_final)

def get_projector_for_each_z(state, z, k):
    """
    Create a projector for the specified control qubit state.
    
    Args:
        state: Statevector to project
        z: Control qubit state (0 or 1)
        
    Returns:
        SparsePauliOp representing the projector
    """
    fidelity_operator = SparsePauliOp.from_operator(state.to_operator())
    identity_op = SparsePauliOp(["I" * k])
    if z == 0:
        # For z=0: Swap q3 to q2 (q2 is the target of the projection)
        control_state = Statevector([1,0])
        control_projector = SparsePauliOp.from_operator(control_state.to_operator())
        return identity_op.tensor(fidelity_operator).tensor(identity_op).tensor(control_projector)
    else:
        assert z == 1
        # For z=1: Keep q3 (q3 is the target of the projection)
        control_state = Statevector([0,1])
        control_projector = SparsePauliOp.from_operator(control_state.to_operator())
        return fidelity_operator.tensor(identity_op).tensor(identity_op).tensor(control_projector)

def estimate_fidelity(qc, state, estimator, k):
    """
    Estimate the fidelity using two projectors (z=0 and z=1).
    
    Args:
        qc: Quantum circuit to estimate
        state: Statevector to project
        estimator: Estimator instance
        k: Number of qubits
        
    Returns:
        Tuple of (fidelity_0, fidelity_1, total_fidelity)
    """
    # Create projectors
    projector_0 = get_projector_for_each_z(state, z=0, k=k)
    projector_1 = get_projector_for_each_z(state, z=1, k=k)
    
    # Apply layout
    layout = qc.layout
    observable_0 = projector_0.apply_layout(layout)
    observable_1 = projector_1.apply_layout(layout)
    
    # Run estimation
    job_0 = estimator.run([(qc, observable_0, None)]).result()
    job_1 = estimator.run([(qc, observable_1, None)]).result()
    
    # Calculate fidelities
    fidelity_0 = job_0[0].data.evs
    fidelity_1 = job_1[0].data.evs
    total_fidelity = fidelity_0 + fidelity_1
    
    return fidelity_0, fidelity_1, total_fidelity

def estimate_original_fidelity(qc,state,estimator,k):
    """
    Estimate the fidelity using two projectors (z=0 and z=1).
    
    Args:
        qc: Quantum circuit to estimate
        state: Statevector to project
        estimator: Estimator instance
        k: Number of qubits
        
    Returns:
        Tuple of (fidelity_0, fidelity_1, total_fidelity)
    """
    fidelity_operator = SparsePauliOp.from_operator(state.to_operator())
    identity_op = SparsePauliOp(["I" * (k)])
    control_identity = SparsePauliOp(["I" * (k)])
    projector = fidelity_operator.tensor(identity_op).tensor(identity_op).tensor(control_identity)

    
    # Apply layout
    layout = qc.layout
    observable = projector.apply_layout(layout)
    
    # Run estimation
    job = estimator.run([(qc, observable, None)]).result()
    
    # Calculate fidelities
    fidelity = job[0].data.evs
    
    return fidelity
# Function to create noise model
def create_noise_model(eps):
    """Create a noise model with depolarizing errors."""
    noise_model = NoiseModel()
    # Add depolarizing error for single qubit gates
    noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 1), ['id_noisy', 'rx'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 2), ['rzz'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 3), ['cswap'])
    readout_error = ReadoutError([[1 - eps, eps], [eps, 1 - eps]])
    noise_model.add_all_qubit_readout_error(readout_error)
    return noise_model

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    k=2
    shots = 10240 
    t = 3.0 
    J = 1.0 
    h = 1.0 
    steps = 5 
    eps_min = 0.0 
    eps_max = 0.1 
    eps_steps = 20
    folder = "data/fidelity_comparison"
    output = "output.png"
    outfile = os.path.join(folder, output)
    trotterized_fidelity = False
    
    # Create output directory
    os.makedirs(folder, exist_ok=True)
    
    # Log parameters
    logging.info(f"Starting simulation with parameters:")
    logging.info(f"Shots: {shots}")
    logging.info(f"Evolution time: {t}")
    logging.info(f"Interaction strength: {J}")
    logging.info(f"Transverse field: {h}")
    logging.info(f"Trotter steps: {steps}")
    logging.info(f"Epsilon range: {eps_min} to {eps_max}")
    logging.info(f"Epsilon steps: {eps_steps}")
    logging.info(f"Using trotterized state: {trotterized_fidelity}")
    
    # Create ising instance
    ising = ising_class(k, steps, t, J, h)  # Using fixed k=2
    
    # Get target state
    if trotterized_fidelity:
        target_state = ising.get_trotterized_ising_statevector()
    else:
        target_state = compute_exact_statevector(k, t, J, h)  # Using fixed k=2
    
    # Arrays to store results
    epsilons = np.linspace(eps_min, eps_max, eps_steps)
    ising_fidelities = []
    qpa_fidelities = []
    original_qpa_nqpa = [0,1,2]
    original_qpa_fidelities= [[] for nqpa in original_qpa_nqpa]
    # Create circuits
    qc_ising = get_QPA_circuit(k, ising, 0)
    qc_qpa = get_QPA_circuit(k, ising, 1)
    original_qc_qpas = [get_original_QPA_circuit(k, ising, nqpa) for nqpa in original_qpa_nqpa]
    # Process each epsilon value with progress bar
    for epsilon in tqdm(epsilons, desc="Processing epsilon values", unit="eps"):
        logging.info(f"\nProcessing epsilon = {epsilon:.3f}")
        
        # Create noise model
        noise_model = create_noise_model(epsilon)
        estimator = AerEstimator(options={
            'backend_options': {
                'noise_model': noise_model,
                'shots': shots
            }
        })
        
        # Estimate Ising circuit fidelity
        _,_,fidelity_ising = estimate_fidelity(qc_ising, target_state, estimator, k)
        ising_fidelities.append(fidelity_ising)
        logging.info(f"Ising fidelity: {fidelity_ising:.4f}")
        
        # Estimate QPA circuit fidelity
        _,_,fidelity_qpa = estimate_fidelity(qc_qpa, target_state, estimator, k)
        qpa_fidelities.append(fidelity_qpa)
        logging.info(f"QPA fidelity: {fidelity_qpa:.4f}")
        for j,(nqpa,original_qc_qpa) in enumerate(zip(original_qpa_nqpa,original_qc_qpas)):
            original_fidelity = estimate_original_fidelity(original_qc_qpa, target_state, estimator, k)
            original_qpa_fidelities[j].append(original_fidelity)
            logging.info(f"QPA fidelity for original QPA {nqpa}: {original_fidelity:.4f}")



    
    # Save raw data
    df = pd.DataFrame({
        'epsilon': epsilons,
        'ising_fidelity': ising_fidelities,
        'qpa_fidelity': qpa_fidelities
    })
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_file = f"data/fidelity_comparison_data_{timestamp}.csv"
    df.to_csv(data_file, index=False)
    logging.info(f"Saved raw data to {data_file}")
    
    # Generate plot
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    plt.plot(epsilons, ising_fidelities, 'o-', label='Ising')
    plt.plot(epsilons, qpa_fidelities, 'x-', label='QPA')
    for j,(nqpa,original_qpa_fidelity) in enumerate(zip(original_qpa_nqpa,original_qpa_fidelities)):
        plt.plot(epsilons, original_qpa_fidelity, 's-', label=f'Original QPA {nqpa}')
    plt.xlabel('Noise Strength (ε)')
    plt.ylabel('Fidelity')
    plt.title('Fidelity Comparison: Ising vs QPA')
    plt.grid(True)
    
    # Construct base folder path using parameters
    base_folder = f"data/estimation_k{k}_shots{shots}_eps{eps_min}-{eps_max}_s{eps_steps}_t{t}_J{J}_h{h}"
    
    # Get all nqpa directories
    nqpa_dirs = [d for d in os.listdir(base_folder)]
    print('Directories of Nqpa under base_folder:', nqpa_dirs)
    # Plot AerEstimator data for each nqpa
    for nqpa_dir in nqpa_dirs:
        nqpa = int(nqpa_dir.split('_')[1][-1])  # Extract nqpa from directory name
        eps_values = []
        fidelities = []
        
        # Get all CSV files in this nqpa directory
        csv_files = [f for f in os.listdir(os.path.join(base_folder, nqpa_dir)) if f.endswith('.csv')]
        
        # Sort CSV files by epsilon value (extracted from filename)
        csv_files.sort(key=lambda x: int(x.split('_')[2].replace('eps', '').replace('.csv', '')))
        
        for csv_file in csv_files:
            df = pd.read_csv(os.path.join(base_folder, nqpa_dir, csv_file))
            eps = df.iloc[0]['epsilon']  # Get epsilon value from CSV
            fidelity = df.iloc[0][f'QPA_{nqpa}']  # Get fidelity value
            eps_values.append(eps)
            fidelities.append(fidelity)
        
        plt.plot(eps_values, fidelities, label=f'AerFidelity {nqpa}', linestyle='--')
    plt.legend()
    plt.savefig(outfile)
    logging.info(f"Saved plot to {outfile}")
    plt.close()

    circuit_path = os.path.join(folder,'circuit_qpa.png')
    circuit_drawer(qc_qpa, output='mpl', filename=circuit_path)
    print(f"[+] Saved original circuit to {circuit_path}")

    circuit_path_original = os.path.join(folder,'circuit_qpa_original.png')
    circuit_drawer(original_qc_qpas[1], output='mpl', filename=circuit_path_original)
    print(f"[+] Saved original circuit to {circuit_path_original}")

if __name__ == '__main__':
    main()
