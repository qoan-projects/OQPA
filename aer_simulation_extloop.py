#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error
import qiskit.circuit.classical as qiskit_classical

def circuit_with_noise_at_end(qc, k, epsilon):
    noise = depolarizing_error(epsilon, k)
    qc.append(noise, range(k, 2*k))
    qc.append(noise, range(2*k, 3*k))
    qc.append(noise, range(3*k, 4*k))
    return qc

def get_QPA_circuit(k, epsilon, N):
    cr = ClassicalRegister(k)
    qr = QuantumRegister(4*k)
    qc = QuantumCircuit(qr, cr)
    qc = circuit_with_noise_at_end(qc, k, epsilon)

    def recursive(N, qc):
        for r in range(k):
            qc.reset(r)
        qc.h(0)
        for r in range(k-1):
            qc.cx(0, 1 + r)
        for r in range(k):
            qc.cswap(0 + r, r + k, r + 2*k)
        for r in range(k):
            qc.h(r)
        for i in range(k):
            qc.measure(i, cr[i])
            parity = qiskit_classical.expr.lift(cr[i]) if i == 0 else qiskit_classical.expr.bit_xor(parity, cr[i])
        with qc.if_test(parity) as _else:
            pass
        with _else:
            for r in range(k):
                qc.swap(r + 2*k, r + 3*k)
            if N != 1:
                qc = recursive(N - 1, qc)
        return qc

    if N > 0:
        qc = recursive(N, qc)
    for i in range(k):
        qc.measure(3*k + i, cr[i])
    qc.save_statevector() # for debugging
    return qc

def run_circuit_explicit(qc, k, num_shots):
    sim = AerSimulator(method='automatic', device='GPU')
    transpiled = transpile(qc, sim)

    count_zeros = 0
    for _ in range(num_shots):
        result = sim.run(transpiled, memory=True).result()
        state = result.get_statevector()
        # print(state)
        # memory = result.get_memory()
        # final_measurement = memory[0]  # single-shot result
        # if final_measurement.endswith('0' * k):
        #     count_zeros += 1
    return count_zeros / num_shots

def main():
    parser = argparse.ArgumentParser(
        description="Run the QPA circuit simulation and evaluate fidelity vs noise strength (λ)."
    )
    parser.add_argument('--k', type=int, default=4,
                        help='Number of qubits in one register (default: 4)')
    parser.add_argument('--shots', type=int, default=10240,
                        help='Number of shots per circuit execution (default: 10240)')
    parser.add_argument('--lambda-min', type=float, default=0.0,
                        help='Minimum λ value (noise strength) to sweep (default: 0.0)')
    parser.add_argument('--lambda-max', type=float, default=1.0,
                        help='Maximum λ value (default: 1.0)')
    parser.add_argument('--lambda-steps', type=int, default=20,
                        help='Number of λ steps between min and max (default: 20)')
    parser.add_argument('--lambda-index', type=int, default=None,
                        help='Use only one λ value by index instead of sweeping (default: None)')
    parser.add_argument('--nqpa', type=int, default=1,
                        help='Number of QPA rounds (default: 1)')
    parser.add_argument('--output', type=str, default='data/fidelity_output.csv',
                        help='Path to output CSV file (default: data/fidelity_output.csv)')
    args = parser.parse_args()

    k = args.k
    shots = args.shots
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    if args.lambda_index is not None:
        lambdas = [lambdas[args.lambda_index]]
    nqpa = args.nqpa

    fidelities = []

    for lam in tqdm(lambdas, desc="Sweeping over λ", unit="λ"):
        with tqdm(total=1, desc=f"λ={lam:.3f}", leave=False) as pbar:
            qc = get_QPA_circuit(k, lam, nqpa)
            fid = run_circuit_explicit(qc, k, shots)
            fidelities.append(fid)
            pbar.update(1)

    df = pd.DataFrame({
        'Lambda': lambdas,
        f'QPA_{nqpa}': fidelities
    })
    df.to_csv(args.output, index=False)
    print(f'[+] Output saved to {args.output}')

if __name__ == '__main__':
    main()