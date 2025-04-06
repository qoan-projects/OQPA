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
            # Even pairs
            for i in range(0, self.d - 1, 2):
                qc.append(RZZGate(-2 * self.J * dt), [i, i + 1])
            # Odd pairs
            for i in range(1, self.d - 1, 2):
                qc.append(RZZGate(-2 * self.J * dt), [i, i + 1])
            # Transverse field
            for i in range(self.d):
                qc.rx(-2 * self.h * dt, i)
        return qc

    def apply_ising_to_registers(self, qc):
        ising = self.get_trotterized_ising_circuit()
        for reg in [1, 2, 3]:
            for gate, qargs, cargs in ising.data:
                mapped_qargs = [qc.qubits[reg * self.d + ising.qubits.index(q)] for q in qargs]
                qc.append(gate, mapped_qargs, cargs)
        return qc

    def get_trotterized_ising_statevector(self):
        qc = self.get_trotterized_ising_circuit()
        qc.save_statevector()
        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def compute_exact_statevector(k, t, J, h):
    """
    Compute the exact statevector for the Ising Hamiltonian:
    H = -J ∑ Z_i Z_{i+1} - h ∑ X_i

    Args:
        k: number of qubits
        t: total evolution time
        J: interaction strength
        h: transverse field strength

    Returns:
        exact_state: Qiskit Statevector object
    """
    dim = 2**k
    I = np.eye(2)
    X = np.array([[0, 1], [1, 0]])
    Z = np.array([[1, 0], [0, -1]])

    def kron_n(*ops):
        out = ops[0]
        for op in ops[1:]:
            out = np.kron(out, op)
        return out

    # Build Hamiltonian
    H = np.zeros((dim, dim), dtype=complex)

    # Z_i Z_{i+1} terms
    for q in range(k - 1):
        ops = [I] * k
        ops[q] = Z
        ops[q + 1] = Z
        H += -J * kron_n(*ops)

    # X_i terms
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

    # Convert to Qiskit Statevector
    return Statevector(psi_final)


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
            qc.append(IGate(label='id_noisy'), [k])
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

def main():
    parser = argparse.ArgumentParser(
        description="Run the QPA-ising circuit simulation and evaluate fidelity vs noise strength (λ)."
    )

    parser.add_argument('--k', type=int, default=3, metavar='NQUBITS',
                        help='Number of qubits per register (default: 3)')
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
    parser.add_argument('--t', type=float, default=5.0,
                        help='Total evolution time for Ising circuit (default: 5.0)')
    parser.add_argument('--J', type=float, default=1.0,
                        help='Interaction strength J (default: 1.0)')
    parser.add_argument('--h', type=float, default=1.0,
                        help='Transverse field h (default: 1.0)')
    parser.add_argument('--steps', type=int, default=5,
                        help='Number of Trotter steps (default: 5)')
    parser.add_argument('--output', type=str, default='data/fidelity_vs_epsilon.csv', metavar='OUTPUT',
                        help='Path to output CSV file (default: data/fidelity_vs_epsilon.csv)')
    args = parser.parse_args()
    k = args.k
    shots = args.shots
    epsilons = np.linspace(args.epsilon_min, args.epsilon_max, args.epsilon_steps)
    if args.epsilon_index is not None:
        epsilons = [epsilons[args.epsilon_index]]
    nqpa = args.nqpa
    t, J, h, steps = args.t, args.J, args.h, args.steps

    ising = ising_class(k, steps, t, J, h)
    exact_state = compute_exact_statevector(k, t, J, h)

    projector_q3 = SparsePauliOp.from_operator(exact_state.to_operator())
    identity_op = SparsePauliOp(["I" * k])
    # pauli_str = "XYZIXZZIYXYZ"
    # full_projector = SparsePauliOp.from_list([(pauli_str, 1)])
    full_projector = projector_q3.tensor(identity_op).tensor(identity_op).tensor(identity_op)
    # full_projector = identity_op.tensor(identity_op).tensor(identity_op).tensor(identity_op)

    # very simple full_projector for debugging, but very slow
    # zero_state = Statevector.from_label("0" * d * 4)
    # full_projector = SparsePauliOp.from_operator(zero_state.to_operator())
    purified_fidelity = []
    # pass_manager = generate_preset_pass_manager(3, AerSimulator())

    for eps in tqdm(epsilons, desc="Sweeping over ε", unit="ε"):
        # t0 = time.perf_counter()
        noise_model = NoiseModel()
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 1), ['id_noisy', 'rx'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 2), ['rzz'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(eps, 3), ['cswap'])
        readout_error = ReadoutError([[1 - eps, eps], [eps, 1 - eps]])
        noise_model.add_all_qubit_readout_error(readout_error)
        estimator = AerEstimator(options={
            'backend_options': {
                'noise_model': noise_model,
                'shots': shots
            }
        })
        #, device = 'GPU'
        
        QPA = get_QPA_circuit(k, nqpa, ising)
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

if __name__ == '__main__':
    main()
