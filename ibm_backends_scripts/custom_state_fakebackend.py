#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
import time
import os
from qiskit.visualization import circuit_drawer

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

        qcSWAP.initialize(input_state, [(reg+1) * k + i for i in range(k)])
    # qcSWAP.initialize(input_states[0], [4,5,6,7])
    # qcSWAP.initialize(input_states[1], [8,9,10,11])
    # qcSWAP.initialize(input_states[2], [12,13,14,15])
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
        description="Run the QPA-ising circuit simulation and evaluate fidelity vs noise strength (λ)."
    )
    parser.add_argument('--k', type=int, default=4, metavar='NQUBITS',
                        help='Number of qubits per register (default: 4)')
    parser.add_argument('--shots', type=int, default=1024, metavar='SHOTS',
                        help='Number of shots per circuit execution (default: 1024)')
    parser.add_argument('--epsilon-min', type=float, default=0.0, metavar='epsilon_MIN',
                        help='Minimum epsilon (noise strength) value to sweep (default: 0.0)')
    parser.add_argument('--epsilon-max', type=float, default=0.009, metavar='epsilon_MAX',
                        help='Maximum epsilon value to sweep (default: 0.009)')
    parser.add_argument('--epsilon-steps', type=int, default=10, metavar='NSTEPS',
                        help='Number of steps between λ_min and λ_max (default: 10)')
    parser.add_argument('--epsilon-index', type=int, default=None,
                        help='Use only one ε value by index instead of sweeping (default: None)')
    parser.add_argument('--nqpa', type=int, default=1, metavar='NQPA',
                    help='Number of QPA rounds to apply (default: 1)')
    parser.add_argument('--state-index', type=int, default=0, metavar='STATE-INDEXX',
                        help='Index of the input state to use (default: 0)')
    parser.add_argument('--datafile', type=str, default='data/input_states.npz', metavar='DATAFILE',
                        help='Path to input state data file (default: data/input_states.npz)')
    parser.add_argument('--exact_state_file', type=str, default='data/exact_state.npz', metavar='EXACT_STATE_FILE',
                        help='Path to exact state data file (default: data/exact_state.npz)')
    parser.add_argument('--output', type=str, default='data/fidelity_vs_epsilon.csv', metavar='OUTPUT',
                        help='Path to output CSV file (default: data/fidelity_vs_epsilon.csv)')
    args = parser.parse_args()
    k = args.k
    shots = args.shots
    epsilons = np.linspace(args.epsilon_min, args.epsilon_max, args.epsilon_steps)
    if args.epsilon_index is not None:
        epsilons = [epsilons[args.epsilon_index]] 
    nqpa = args.nqpa


    input_index = args.state_index
    datafile = args.datafile
    data = np.load(datafile, allow_pickle=True)
    input_states = data["states"][input_index]
    
    
    exact_state_file = args.exact_state_file
    exact_state_data = np.load(exact_state_file, allow_pickle=True)
    exact_state = exact_state_data["state"]

    projector_q3 = SparsePauliOp.from_operator(Statevector(exact_state).to_operator())
    identity_op = SparsePauliOp(["I" * k])
    full_projector = projector_q3.tensor(identity_op).tensor(identity_op).tensor(identity_op)
    purified_fidelity = []
    # pass_manager = generate_preset_pass_manager(3, AerSimulator())

    for eps in tqdm(epsilons, desc="Sweeping over ε", unit="ε"):
        # t0 = time.perf_counter()
        # noise_model = NoiseModel()
        # noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 1), ['id_noisy', 'rx'])
        # noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 2), ['rzz'])
        # noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 3), ['cswap'])
        # readout_error = ReadoutError([[1 - eps, eps], [eps, 1 - eps]])
        # noise_model.add_all_qubit_readout_error(readout_error)
        noise_model = NoiseModel()
        eps_1q = eps
        eps_2q = min(30 * eps, 1.0)
        eps_3q = min(100 * eps, 1.0)
        print(f'Using noise model of: eps_1q:{eps_1q}, eps_2q:{eps_2q}, eps_3q:{eps_3q}')
        # 1-qubit gates (ε)
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps_1q, 1), ['id_noisy', 'rx'])

        # 2-qubit gates (30ε)
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps_2q, 2), ['rzz'])

        # 3-qubit gates (100ε)
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps_3q, 3), ['cswap'])

        # Readout error (still ε)
        readout_error = ReadoutError([[1 - eps, eps], [eps, 1 - eps]])
        noise_model.add_all_qubit_readout_error(readout_error)
    
        estimator = AerEstimator(options={
            'backend_options': {
                'noise_model': noise_model,
                'shots': shots
            }
        })
        #, device = 'GPU'
        
        QPA = get_QPA_circuit(k, nqpa, input_states)
        # isa_circuit = pass_manager.run(QPA)
        # qc_transpiled = transpile(isa_circuit)

        # t1 = time.perf_counter()
        result = estimator.run([(QPA, full_projector, None)]).result()
        # t2 = time.perf_counter()
        fidelity = result[0].data.evs
        purified_fidelity.append(fidelity)
        
        # print(f"Delta t1: {t1 - t0:.3f} sec", flush=True)
        # print(f"Delta t2: {t2 - t1:.3f} sec", flush=True)

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame({
    'epsilon': list(epsilons),
    f'QPA_{args.nqpa}': purified_fidelity
    })
    df.to_csv(args.output, index=False)
    print(f'[+] Output saved to {args.output}')
    if args.epsilon_index==0:
        circuit_path = args.output.replace(".csv", "_original.png")
        circuit_drawer(QPA, output='mpl', filename=circuit_path)
        print(f"[+] Saved original circuit to {circuit_path}")
if __name__ == '__main__':
    main()
