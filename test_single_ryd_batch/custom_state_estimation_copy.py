#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
import time
import os

from scipy.linalg import expm
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.quantum_info import (
    Statevector,
    SparsePauliOp
)
from qiskit_aer import AerSimulator
import qiskit.circuit.classical as qiskit_classical
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
from qiskit_aer.noise import (
    NoiseModel,
    QuantumError,
    ReadoutError,
    depolarizing_error,
    pauli_error,
    thermal_relaxation_error,
)
from qiskit.circuit.library import RZZGate, IGate


import numpy as np
import sys



# Continue to run the simulation using input_states
# You already have this part in your existing code

def get_QPA_circuit(k, N, input_states):
    cr_q0 = ClassicalRegister(k, name='control')
    qr_all = QuantumRegister(4 * k)
    qcSWAP = QuantumCircuit(qr_all, cr_q0)

    for reg in range(3):
        input_state = input_states[reg]
        qcSWAP.initialize(input_state, [reg * k + i for i in range(k)])
    qc = qcSWAP

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

def main():
    parser = argparse.ArgumentParser(
        description="Run the QPA circuit simulation and evaluate fidelity at a fixed noise level (ε)."
    )
    parser.add_argument('--k', type=int, default=4,
                        help='Number of qubits per register (default: 4)')
    parser.add_argument('--shots', type=int, default=1024,
                        help='Number of shots per circuit execution (default: 1024)')
    parser.add_argument('--epsilon', type=float, required=True,
                        help='Noise strength (epsilon) to apply')
    parser.add_argument('--nqpa', type=int, default=1,
                        help='Number of QPA rounds to apply (default: 1)')
    parser.add_argument('--state-index', type=int, default=0,
                        help='Index of the input state to use (default: 0)')
    parser.add_argument('--datafile', type=str, default='data/input_states.npz',
                        help='Path to input state data file')
    parser.add_argument('--exact_state_file', type=str, default='data/exact_state.npz',
                        help='Path to exact state data file')
    parser.add_argument('--output', type=str, default='data/fidelity_vs_epsilon.csv',
                        help='Path to output CSV file')

    args = parser.parse_args()
    k = args.k
    shots = args.shots
    epsilon = args.epsilon
    nqpa = args.nqpa
    #print all parameters
    print("k:", k)
    print("shots:", shots)
    print("epsilon:", epsilon)
    print("nqpa:", nqpa)
    #Print paths
    print("datafile:", args.datafile)
    print("exact_state_file:", args.exact_state_file)
    print("output:", args.output)
    # Load input state
    data = np.load(args.datafile, allow_pickle=True)
    input_states = data["states"][args.state_index]

    # Load exact state
    exact_state_data = np.load(args.exact_state_file, allow_pickle=True)
    exact_state = exact_state_data["state"]

    # Create full projector
    projector_q3 = SparsePauliOp.from_operator(Statevector(exact_state).to_operator())
    identity_op = SparsePauliOp(["I" * k])
    full_projector = projector_q3.tensor(identity_op).tensor(identity_op).tensor(identity_op)

    # Set up noise model
    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(depolarizing_error(epsilon, 1), ['id_noisy', 'rx'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(epsilon, 2), ['rzz'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(epsilon, 3), ['cswap'])
    readout_error = ReadoutError([[1 - epsilon, epsilon], [epsilon, 1 - epsilon]])
    noise_model.add_all_qubit_readout_error(readout_error)

    estimator = AerEstimator(options={
        'backend_options': {
            'noise_model': noise_model,
            'shots': shots
        }
    })

    # Build and run circuit
    QPA = get_QPA_circuit(k, nqpa, input_states)
    result = estimator.run([(QPA, full_projector, None)]).result()
    fidelity = result[0].data.evs

    # Save result
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df = pd.DataFrame({'epsilon': [epsilon], f'QPA_{nqpa}': [fidelity]})
    df.to_csv(args.output, index=False)
    print(f'[+] Output saved to {args.output}')

if __name__ == '__main__':
    main()
