#!/usr/bin/env python3
"""
QPA-ising circuit simulation with simplified implementation.

This implementation uses:
- k=2 qubits per register
- Single control qubit
- Single QPA sequence (H, CSWAP, H)
- Two projectors for z=0 and z=1 states
"""

import numpy as np
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit.quantum_info import Statevector, Operator, SparsePauliOp
from qiskit_aer import AerSimulator
import os
from qiskit.visualization import circuit_drawer
import argparse
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
import pandas as pd
from scipy.linalg import expm
from dotenv import load_dotenv
from qiskit_ibm_runtime import QiskitRuntimeService, EstimatorV2

# Load IBM Quantum credentials
load_dotenv()
token = os.getenv("IBM_QUANTUM_TOKEN")

# Constants
K = 2  # Fixed number of qubits per register

class ladder_class:
    """
    Class for generating Ising model circuits and statevectors.
    
    Args:
        d: Number of qubits per register
        steps: Number of Trotter steps
        t: Evolution time
        J: Interaction strength
        h: Transverse field strength
    """
    def __init__(self, d):
        self.d = d
        assert d==2
    def get_ladder_circuit(self):
        """
        Returns a QuantumCircuit implementing a trotterized Ising evolution.
        """
        qc = QuantumCircuit(self.d)
        qc.rx(np.pi/4, 0)
        qc.cx(0, 1)
        qc.ry(np.pi/3, 1)
        qc.cx(1, 0)
        qc.rz(np.pi/5, 0)
        qc.cx(0, 1)
        qc.rx(np.pi/3, 0)
        qc.cx(0, 1)
        qc.ry(np.pi/4, 1)
        qc.cx(1, 0)
        qc.rz(np.pi/5, 0)
        qc.cx(0, 1)
        qc.rx(np.pi/3, 0)
        qc.cx(0, 1)
        qc.ry(np.pi/4, 1)
        qc.cx(1, 0)
        qc.rz(np.pi/5, 0)
        return qc

    def apply_ladder_to_registers(self, qc, start):
        """
        Apply trotterized Ising circuit to registers q1, q2, q3.
        """
        ladder = self.get_ladder_circuit()
        ladder_inst = ladder.to_instruction()
        
        for reg in [1, 2, 3]:
            qc.append(ladder_inst, [(reg-1) * self.d + i + start for i in range(self.d)])
        
        return qc

    def get_ladder_statevector(self):
        """
        Returns the statevector from the trotterized Ising evolution.
        """
        qc = self.get_ladder_circuit()
        qc.save_statevector()
        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def get_QPA_circuit(d, ladder_circuit, nqpa):
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
    qc = ladder_circuit.apply_ladder_to_registers(qc, start=1)
    if nqpa==0:
        return qc

    assert nqpa==1 #Cannot have a different value for this circuit for now
    
    # Single QPA sequence
    qc.h(0)      # Apply Hadamard
    for k in range(d):
        qc.cswap(0, k+1, k+d+1)  # Control qubit 0, target q1 and q2
    qc.h(0)      # Apply second Hadamard
    
    return qc

def get_projector_for_each_z(state, z):
    """
    Create a projector for the specified control qubit state.
    
    Args:
        state: Statevector to project
        z: Control qubit state (0 or 1)
        
    Returns:
        SparsePauliOp representing the projector
    """
    fidelity_operator = SparsePauliOp.from_operator(state.to_operator())
    identity_op = SparsePauliOp(["I" * K])  # Using constant K=2
    
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

def estimate_fidelity(qc, state, shots,backend):
    """
    Estimate the fidelity using two projectors (z=0 and z=1).
    
    Args:
        qc: Quantum circuit to estimate
        state: Statevector to project
        backend: Backend to use
        shots: Number of shots
        
    Returns:
        Tuple of (fidelity_0, fidelity_1, total_fidelity)
    """
    # Create projectors
    projector_0 = get_projector_for_each_z(state, z=0)
    projector_1 = get_projector_for_each_z(state, z=1)
    
    # Apply layout
    layout = qc.layout
    observable_0 = projector_0.apply_layout(layout)
    observable_1 = projector_1.apply_layout(layout)
    
    # Create estimator
    estimator = EstimatorV2(mode=backend)
    estimator.options.default_shots = shots
    
    # Run estimation
    job_0 = estimator.run([(qc, observable_0, None)]).result()
    job_1 = estimator.run([(qc, observable_1, None)]).result()
    
    # Calculate fidelities
    fidelity_0 = job_0[0].data.evs
    fidelity_1 = job_1[0].data.evs
    total_fidelity = fidelity_0 + fidelity_1
    
    return fidelity_0, fidelity_1, total_fidelity

def save_circuit_images(qc, out_path):
    circuit_drawer(qc, output='mpl', filename=out_path)

def main():
    """
    Main function to run the QPA-ising circuit simulation.
    """
    parser = argparse.ArgumentParser(
        description="Run the QPA-ising circuit simulation and evaluate fidelity."
    )
    parser.add_argument('--nqpa', type=float, default=0,
                      help='Number of QPA cycles done (default: 0)')
    parser.add_argument('--shots', type=int, default=1024,
                        help='Number of shots per circuit execution (default: 1024)')
    parser.add_argument('--output', type=str, default='data/fidelity_fake_backend.csv',
                        help='Output CSV file path')
    args = parser.parse_args()
    k = K  # Using constant K=2
    shots = args.shots
    nqpa = args.nqpa
    
    print('k:', k)
    print('shots:', shots)
    print('Doing QPA with nqpa:', nqpa)

    # Set up output paths
    out_path = args.output
    dir_name, base_name = os.path.split(out_path)
    prefix = "Ladder_Fidelity"
    new_base = f"{prefix}_{base_name}"
    out_path = os.path.join(dir_name, new_base)
    out_path_transpiled_circuit = os.path.splitext(out_path)[0] + "_transpiled.png"
    out_path_original_circuit = os.path.splitext(out_path)[0] + "_original.png"
    # Initialize backend and IBM service
    service = QiskitRuntimeService()
    backend = FakeSherbrooke()

    # Initialize Ising circuit
    ladder = ladder_class(k)
    
    # Get statevector
    state = ladder.get_ladder_statevector()
    
    # Create and transpile circuit
    QPA_fake = get_QPA_circuit(k, ladder, nqpa)
    qc_transpiled = transpile(QPA_fake, backend=backend, optimization_level=3)

    # Save circuit images
    save_circuit_images(QPA_fake, out_path_original_circuit)
    save_circuit_images(qc_transpiled, out_path_transpiled_circuit)

    # Estimate fidelity
    fidelities = []
    nqpa_list = [nqpa]
    fidelity_0, fidelity_1, total_fidelity = estimate_fidelity(qc_transpiled, state, shots,backend)
    
    print(f'Fidelities: |0><0|={fidelity_0}, |1><1|={fidelity_1}, total={total_fidelity}')
    fidelities.append(total_fidelity)

    # Save results
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame({
        'nqpa_list': list(nqpa_list),
        'Fidelities': fidelities
    })
    df.to_csv(out_path, index=False)
    print(f'[+] Output saved to {out_path}')

if __name__ == '__main__':
    main()