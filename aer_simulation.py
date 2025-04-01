#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
from tqdm import tqdm
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error
import qiskit.circuit.classical as qiskit_classical

def circuit_with_noise_at_end(qc, d, epsilon):
    noise = depolarizing_error(epsilon, d)
    qc.append(noise, range(d, 2*d))
    qc.append(noise, range(2*d, 3*d))
    qc.append(noise, range(3*d, 4*d))
    return qc

def get_QPA_circuit(d, epsilon, N):
    cr = ClassicalRegister(d)
    qr = QuantumRegister(4*d)
    qc = QuantumCircuit(qr, cr)
    qc = circuit_with_noise_at_end(qc, d, epsilon)

    def recursive(N, qc):
        for k in range(d):
            qc.reset(k)
        qc.h(0)
        for k in range(d-1):
            qc.cx(0, 1 + k)
        for k in range(d):
            qc.cswap(0 + k, k + d, k + 2*d)
        for k in range(d):
            qc.h(k)
        for i in range(d):
            qc.measure(i, cr[i])
            parity = qiskit_classical.expr.lift(cr[i]) if i == 0 else qiskit_classical.expr.bit_xor(parity, cr[i])
        with qc.if_test(parity) as _else:
            pass
        with _else:
            for k in range(d):
                qc.swap(k + 2*d, k + 3*d)
            if N != 1:
                qc = recursive(N - 1, qc)
        return qc

    if N > 0:
        qc = recursive(N, qc)
    for i in range(d):
        qc.measure(3*d + i, cr[i])
    return qc

def run_circuit(qc, shots):
    sim = AerSimulator(method='statevector', device='GPU')
    transpiled = transpile(qc, sim)
    result = sim.run(transpiled, shots=shots, memory=True).result()
    return result.get_memory()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--d', type=int, default=4)
    parser.add_argument('--shots', type=int, default=10240)
    parser.add_argument('--lambda-min', type=float, default=0.0)
    parser.add_argument('--lambda-max', type=float, default=1.0)
    parser.add_argument('--lambda-steps', type=int, default=20)
    parser.add_argument('--nqpa', type=int, default=1)
    parser.add_argument('--output', type=str, default='data/fidelity_output.csv')
    args = parser.parse_args()

    d = args.d
    shots = args.shots
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    nqpa = args.nqpa

    fidelities = []

    for lam in tqdm(lambdas, desc="Sweeping over λ", unit="λ"):
        with tqdm(total=1, desc=f"λ={lam:.3f}", leave=False) as pbar:
            qc = get_QPA_circuit(d, lam, nqpa)
            memory = run_circuit(qc, shots)
            fid = memory.count('0' * d) / len(memory)
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