#!/usr/bin/env python3
"""
QPA-ising circuit simulation with simplified implementation.

This implementation uses:
- k=2 qubits per register
- Single control qubit
- Single QPA sequence (H, CSWAP, H)
- Two projectors for z=0 and z=1 states
"""
from itertools import product
import numpy as np
from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit.quantum_info import Statevector, Operator, SparsePauliOp
from qiskit_aer import AerSimulator
import os
from qiskit.visualization import circuit_drawer
import argparse
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeMarrakesh
import pandas as pd
from scipy.linalg import expm
from dotenv import load_dotenv
from qiskit_ibm_runtime import QiskitRuntimeService, EstimatorV2, SamplerV2
from qiskit_aer.primitives import SamplerV2 as AerSampler
from qiskit_aer.noise import (
    NoiseModel,
    QuantumError,
    ReadoutError,
    depolarizing_error,
    pauli_error,
    thermal_relaxation_error,
)

from tqdm import tqdm


def get_QPA_circuit_1(k, LAMBDA):
    # Two control qubit
    cr = ClassicalRegister(2*k+2, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 2)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(2, 2 + k), range(2+ k, 2+2 * k), range(2+2 * k, 2+3 * k)]
    pauli_strs = ['i', 'x', 'y', 'z']

    for reg in reg_ranges:
        if rng.random() < LAMBDA:
            paulis = rng.choice(pauli_strs, size=k)
            for q, p in zip(reg, paulis):
                if p == 'x':
                    qc.x(q)
                elif p == 'y':
                    qc.y(q)
                elif p == 'z':
                    qc.z(q)
    
    # Single QPA sequence
    qc.h(0)
    for i in range(k):
            qc.cswap(0, i+2, i+k+2)  # Control qubit 0, target q1 and q2
    qc.h(0)
    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    for i in range(k): #Measure Q2
        qc.measure(2+k+i,cr[2+i])
    for i in range(k): #Measure Q3
        qc.measure(2+2*k+i,cr[2+k+i])
    return qc

def get_QPA_circuit_2(k, LAMBDA):
    # Two control qubit
    cr = ClassicalRegister(2*k+2, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 2)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(2, 2 + k), range(2+ k, 2+2 * k), range(2+2 * k, 2+3 * k)]
    pauli_strs = ['i', 'x', 'y', 'z']

    for reg in reg_ranges:
        if rng.random() < LAMBDA:
            paulis = rng.choice(pauli_strs, size=k)
            for q, p in zip(reg, paulis):
                if p == 'x':
                    qc.x(q)
                elif p == 'y':
                    qc.y(q)
                elif p == 'z':
                    qc.z(q)
    
    # Single QPA sequence
    qc.h(0)
    for i in range(k):
            qc.cswap(0, i+2, i+k+2)  # Control qubit 0, target q1 and q2
    qc.h(0)

    qc.h(1)
    for i in range(k):
            qc.cswap(1, i+2, i+2*k+2)  # Control qubit 1, target q1 and q3
    qc.h(1)

    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    for i in range(k): #Measure Q2
        qc.measure(2+k+i,cr[2+i])
    for i in range(k): #Measure Q3
        qc.measure(2+2*k+i,cr[2+k+i])
    return qc

def save_circuit_images(qc, out_path):
    circuit_drawer(qc, output='mpl', filename=out_path)

def good_bitstrings1(k):
    """Returns good bitstrings for circuit 1 where q3 == '0'*k and z == '1'."""
    good_bitstrings = []
    q3 = '0' * k
    for q2 in range(2**k):
        q2_bits = f"{q2:0{k}b}"
        for zp in ['0', '1']:
            bitstring = q3 + q2_bits + zp + '1'  # z = 1
            good_bitstrings.append(bitstring)
    return good_bitstrings

def good_bitstrings2(k):
    """
    Returns good bitstrings for circuit 2:
    - Case 1: q3 == '0'*k and z == '0' and zp == '0'
    - Case 2: q2 == '0'*k and z == '0' and zp == '1'
    """
    good_bitstrings = []
    q2_zero = '0' * k
    q3_zero = '0' * k

    # Case 1
    for q2 in range(2**k):
        q2_bits = f"{q2:0{k}b}"
        bitstring = q3_zero + q2_bits + '0' + '0'  # zp=0, z=0
        good_bitstrings.append(bitstring)

    # Case 2
    for q3 in range(2**k):
        q3_bits = f"{q3:0{k}b}"
        bitstring = q3_bits + q2_zero + '1' + '0'  # zp=1, z=0
        good_bitstrings.append(bitstring)

    return good_bitstrings

def print_bitstrings(bitstrings, k):
    for b in bitstrings:
        q3 = b[:k]
        q2 = b[k:2*k]
        zp = b[2*k]
        z = b[2*k+1]
        print(f"q3={q3}, q2={q2}, z={z}, zp={zp}")

    

def get_fidelity_from_paulis(qc_list, shots,sampler,backend,accepted_bitstrings):
    #RUN THE CIRCUIT AND MEASURE CLASSICALLY THE STATE IN REGISTER Q3, SHOULD RETURN A SEQUENCE OF BITS OF d DIMENSIONS FOR EACH SHOT, REPRESENTING THE FINAL STATE MEASURED
    # pass_manager = generate_preset_pass_manager(3, AerSimulator())
    # isa_circuit_list = pass_manager.run(qc_list)
    # qc_transpiled_list = transpile(isa_circuit_list)
    qc_transpiled_list = transpile(qc_list, backend=backend, optimization_level=3)
    result = sampler.run(qc_transpiled_list,shots=shots).result()
    fid=0
    for i in range(len(qc_list)):
        pub_result = result[i]
        counts = pub_result.data.control.get_counts()
        fidelity = sum(counts.get(bitstring, 0) for bitstring in accepted_bitstrings)/shots
        fid+=fidelity
    fid=fid/len(qc_list)
    return fid

def main():
    """
    Main function to run the QPA-ising circuit simulation.
    """
    parser = argparse.ArgumentParser(
        description="Run the QPA-ising circuit simulation and evaluate fidelity vs noise strength (λ)."
    )
    parser.add_argument('--k', type=int, default=2, metavar='NQUBITS',
                        help='Number of qubits per register (default: 2)')
    parser.add_argument('--shots', type=int, default=1024, metavar='SHOTS',
                        help='Number of shots per circuit execution (default: 1024)')
    parser.add_argument('--lambda-min', type=float, default=0.0, metavar='lambda_MIN',
                        help='Minimum lambda (noise strength) value to sweep (default: 0.0)')
    parser.add_argument('--lambda-max', type=float, default=0.009, metavar='lambda_MAX',
                        help='Maximum lambda value to sweep (default: 0.009)')
    parser.add_argument('--lambda-steps', type=int, default=10, metavar='NSTEPS',
                        help='Number of steps between lambda_min and lambda_max (default: 10)')
    parser.add_argument('--lambda-index', type=int, default=None,
                        help='Use only one ε value by index instead of sweeping (default: None)')
    parser.add_argument('--nqpa', type=int, default=1, metavar='NQPA',
                    help='Number of QPA rounds to apply (default: 1)')
    parser.add_argument('--nrandom', type=int, default=1, metavar='NRANDOM',
                    help='Number of Circuits to be randomized (default: 1)')
    parser.add_argument('--gatenoise', type=float, default=0.05, metavar='GATENOISE',
                        help='Gate noise strength (default: 0.05)')

    parser.add_argument('--aertesting', type=lambda x: (str(x).lower() == 'true'), default=False,
                        help='Use AerSimulator instead of IBM backend (default: False)')
    parser.add_argument('--faketesting', type=lambda x: (str(x).lower() == 'true'), default=False,
                        help='Use FakeSherbrooke instead of IBM backend (default: False)')
    parser.add_argument('--output', type=str, default='data/fidelity_vs_lambda.csv', metavar='OUTPUT',
                        help='Path to output CSV file (default: data/fidelity_vs_lambda.csv)')
    args = parser.parse_args()
    k = args.k
    N_qpa = args.nqpa
    assert N_qpa == 2
    total_shots = args.shots
    n_random = args.nrandom
    shots = round(total_shots/n_random)
    gatenoise = args.gatenoise
    aer_testing = args.aertesting
    fake_testing = args.faketesting
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    if args.lambda_index is not None:
        lambdas = [lambdas[args.lambda_index]]

    purified_fidelity = []
    if aer_testing == True:
        print(f'Using AER Sampler for testing because aer_testing={aer_testing}')
        backend = AerSimulator()
        noise_model = NoiseModel()
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 1), ['id_noisy', 'rx'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 2), ['rzz'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 3), ['cswap'])
        readout_error = ReadoutError([[1 - gatenoise, gatenoise], [gatenoise, 1 - gatenoise]])
        noise_model.add_all_qubit_readout_error(readout_error)
        sampler = AerSampler(options=dict(backend_options=dict(noise_model=noise_model)))
    elif fake_testing == True:
        print(f'Using FakeBackend for testing because fake_testing={fake_testing}')
        # backend = FakeSherbrooke()
        backend = FakeMarrakesh()
        sampler = SamplerV2(mode=backend)
    else:
        #Load IBM Quantum credentials
        print('Using IBM Sampler')
        print(f'Using n={shots} shots into each circuit')
        load_dotenv()
        token = os.getenv("IBM_QUANTUM_TOKEN")
        service = QiskitRuntimeService(channel="ibm_quantum",instance='research-credits/100698/main',token=token)
        # service = QiskitRuntimeService(channel="ibm_quantum",instance='ibm-q/open/main',token=token)
        # backend = service.backend("ibm_aachen")
        # backend = service.backend("ibm_kingston")
        # backend = service.backend("ibm_sherbrooke")
        backend = service.backend("ibm_marrakesh")
        sampler = SamplerV2(mode=backend)
    for lambda_val in tqdm(lambdas, desc="Sweeping over λ", unit="λ"):
        # t0 = time.perf_counter()
        QPA1_list = []
        QPA2_list = []
        for _ in range(n_random):
            QPA1= get_QPA_circuit_1(k, lambda_val)
            QPA2= get_QPA_circuit_2(k, lambda_val)
            QPA1_list.append(QPA1)
            QPA2_list.append(QPA2)
        if args.lambda_index==0:
            QPA1_for_draw = get_QPA_circuit_1(k, 0)
            QPA2_for_draw = get_QPA_circuit_2(k, 0)
            circuit_path1 = args.output.replace(".csv", "_1_original.png")
            circuit_path2 = args.output.replace(".csv", "_2_original.png")
            circuit_drawer(QPA1_for_draw, output='mpl', filename=circuit_path1)
            circuit_drawer(QPA2_for_draw, output='mpl', filename=circuit_path2)
            print(f"[+] Saved original circuit1 to {circuit_path1}")
            print(f"[+] Saved original circuit2 to {circuit_path2}")
            
        
        accepted_bitstrings1=good_bitstrings1(k)
        accepted_bitstrings2=good_bitstrings2(k)
        
        fidelity1 = get_fidelity_from_paulis(QPA1_list, shots,sampler,backend,accepted_bitstrings1)
        fidelity2 = get_fidelity_from_paulis(QPA2_list, shots,sampler,backend,accepted_bitstrings2)
        fidelity=fidelity1+fidelity2

        purified_fidelity.append(fidelity)
        print(fidelity)
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame({
    'lambda': list(lambdas),
    f'QPA_{args.nqpa}': purified_fidelity
    })
    df.to_csv(args.output, index=False)
    print(f'[+] Output saved to {args.output}')
    
    # psi_purified = run_qc_and_return_state(QPA)
    #print(transpile(QPA).draw())
    # display(psi_purified.draw('latex'))
if __name__ == '__main__':
    main()