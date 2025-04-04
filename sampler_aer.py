#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
import time
import os

from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.quantum_info import (
    Kraus, SuperOp, Statevector, DensityMatrix, state_fidelity,
    partial_trace, Operator, SparsePauliOp
)
from qiskit_aer import AerSimulator
import qiskit.circuit.classical as qiskit_classical
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
from qiskit_aer.noise import (
    NoiseModel, QuantumError, ReadoutError,
    depolarizing_error, pauli_error, thermal_relaxation_error
)

class ising_class:
    def __init__(self, d, steps, t, J, h):
        self.d = d
        self.steps = steps
        self.t = t
        self.J = J
        self.h = h

    def get_trotterized_ising_circuit(self):
        dt = self.t / self.steps
        qc = QuantumCircuit(self.d)
        for _ in range(self.steps):
            for i in range(self.d - 1):
                qc.cx(i, i + 1)
                qc.rz(-2 * self.J * dt, i + 1)
                qc.cx(i, i + 1)
            for i in range(self.d):
                qc.rx(-2 * self.h * dt, i)
        return qc

    def apply_ising_to_registers(self, qc):
        ising = self.get_trotterized_ising_circuit()
        ising_inst = ising.to_instruction()
        for reg in [1, 2, 3]:
            qc.append(ising_inst, [reg * self.d + i for i in range(self.d)])
        return qc

    def get_trotterized_ising_statevector(self):
        qc = self.get_trotterized_ising_circuit()
        qc.save_statevector()
        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def get_QPA_circuit(d, N, ising_circuit):
    cr_q0 = ClassicalRegister(d, name='control')
    qr_all = QuantumRegister(4 * d)
    qcSWAP = QuantumCircuit(qr_all, cr_q0)
    qc = ising_circuit.apply_ising_to_registers(qcSWAP)

    def recursive(N, qc):
        for k in range(d):
            qc.reset(k)
        qc.h(0)
        for k in range(d - 1):
            qc.cx(0, 1 + k)
        for k in range(d):
            qc.cswap(0 + k, k + d, k + 2 * d)
        for k in range(d):
            qc.h(k)
        for i in range(d):
            qc.measure(i, cr_q0[i])
            if i == 0:
                parity_control = qiskit_classical.expr.lift(cr_q0[i])
            else:
                parity_control = qiskit_classical.expr.bit_xor(parity_control, cr_q0[i])
        with qc.if_test(parity_control) as _else:
            pass
        with _else:
            for k in range(d):
                qc.swap(k + 2 * d, k + 3 * d)
            if N != 1:
                qc = recursive(N - 1, qc)
        return qc

    if N != 0:
        qc = recursive(N, qcSWAP)
    else:
        qc = qcSWAP
    return qc

def estimate_qc_and_return_distribution(qc, observables, estimator):
    pass_manager = generate_preset_pass_manager(3, AerSimulator())
    isa_circuit = pass_manager.run(qc)
    qc_transpiled = transpile(isa_circuit)
    result = estimator.run([(qc_transpiled, observables, None)]).result()
    return result[0].data.evs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--d', type=int, default=3)
    parser.add_argument('--shots', type=int, default=4096)
    parser.add_argument('--lambda-min', type=float, default=0.0)
    parser.add_argument('--lambda-max', type=float, default=0.009)
    parser.add_argument('--lambda-steps', type=int, default=10)
    parser.add_argument('--nqpa', nargs='+', type=int, default=[0,1,2])
    parser.add_argument('--output', type=str, default='data/fidelity_vs_lambda.csv')
    args = parser.parse_args()

    t, J, h, steps = 5.0, 1, 1, 5
    d = args.d
    shots = args.shots
    list_of_noise = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    list_of_Nqpa = args.nqpa

    ising = ising_class(d, steps, t, J, h)
    trotterized_state = ising.get_trotterized_ising_statevector()

    projector_q3 = SparsePauliOp.from_operator(trotterized_state.to_operator())
    identity_op = SparsePauliOp(["I" * d])
    full_projector = projector_q3.tensor(identity_op).tensor(identity_op).tensor(identity_op)

    purified_fidelity = {i: [] for i in list_of_Nqpa}
    pass_manager = generate_preset_pass_manager(3, AerSimulator())

    for noise in tqdm(list_of_noise, desc="Sweeping over λ", unit="λ"):
        noise_model = NoiseModel()
        noise_model.add_all_qubit_quantum_error(depolarizing_error(noise, 1), ['h', 'x', 'rx', 'rz'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(noise, 2), ['cx'])
        estimator = AerEstimator(options=dict(backend_options=dict(noise_model=noise_model, shots=shots)))

        for Nqpa in list_of_Nqpa:
            QPA = get_QPA_circuit(d, Nqpa, ising)
            isa_circuit = pass_manager.run(QPA)
            qc_transpiled = transpile(isa_circuit)
            result = estimator.run([(qc_transpiled, full_projector, None)]).result()
            fidelity = result[0].data.evs
            purified_fidelity[Nqpa].append(fidelity)

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame({f'Nqpa={k}': purified_fidelity[k] for k in list_of_Nqpa})
    df.insert(0, "Lambda", list(list_of_noise))
    df.to_csv(args.output, index=False)
    print(f'[+] Output saved to {args.output}')

if __name__ == '__main__':
    main()
