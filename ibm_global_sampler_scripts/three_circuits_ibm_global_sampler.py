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
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def get_QPA_circuit_0(k, LAMBDA):
    # Three control qubit
    cr = ClassicalRegister(2*k+3, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 3)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(3, 3 + k), range(3+ k, 3+2 * k), range(3+2 * k, 3+3 * k)]
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
    
    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    qc.measure(2,cr[2])
    for i in range(k): #Measure Q2
        qc.measure(3+k+i,cr[3+i])
    for i in range(k): #Measure Q3
        qc.measure(3+2*k+i,cr[3+k+i])
    return qc
    
def get_QPA_circuit_1(k, LAMBDA):
    # Three control qubit
    cr = ClassicalRegister(2*k+3, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 3)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(3, 3 + k), range(3+ k, 3+2 * k), range(3+2 * k, 3+3 * k)]
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
            qc.cswap(0, i+3, i+k+3)  # Control qubit 0, target q1 and q2
    qc.h(0)
    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    qc.measure(2,cr[2])
    for i in range(k): #Measure Q2
        qc.measure(3+k+i,cr[3+i])
    for i in range(k): #Measure Q3
        qc.measure(3+2*k+i,cr[3+k+i])
    return qc

def get_QPA_circuit_2(k, LAMBDA):
    # Three control qubit
    cr = ClassicalRegister(2*k+3, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 3)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(3, 3 + k), range(3+ k, 3+2 * k), range(3+2 * k, 3+3 * k)]
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
            qc.cswap(0, i+3, i+k+3)  # Control qubit 0, target q1 and q2
    qc.h(0)

    qc.h(1)
    for i in range(k):
            qc.cswap(1, i+3, i+2*k+3)  # Control qubit 1, target q1 and q3
    qc.h(1)

    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    qc.measure(2,cr[2])
    for i in range(k): #Measure Q2
        qc.measure(3+k+i,cr[3+i])
    for i in range(k): #Measure Q3
        qc.measure(3+2*k+i,cr[3+k+i])
    return qc
def get_QPA_circuit_3(k, LAMBDA):
    # Three control qubit
    cr = ClassicalRegister(2*k+3, name='control') #Will only Measure q3
    qr_all = QuantumRegister(3*k + 3)
    
    # Initialize quantum circuit
    qc = QuantumCircuit(qr_all, cr)

    rng = np.random.default_rng()

    reg_ranges = [range(3, 3 + k), range(3+ k, 3+2 * k), range(3+2 * k, 3+3 * k)]
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
            qc.cswap(0, i+3, i+k+3)  # Control qubit 0, target q1 and q2
    qc.h(0)

    qc.h(1)
    for i in range(k):
            qc.cswap(1, i+3, i+2*k+3)  # Control qubit 1, target q1 and q3
    qc.h(1)

    qc.h(2)
    for i in range(k):
            qc.cswap(2, i+3, i+k+3)  # Control qubit 2, target q1 and q2
    qc.h(2)

    qc.measure(0,cr[0])
    qc.measure(1,cr[1])
    qc.measure(2,cr[2])
    for i in range(k): #Measure Q2
        qc.measure(3+k+i,cr[3+i])
    for i in range(k): #Measure Q3
        qc.measure(3+2*k+i,cr[3+k+i])
    return qc

def save_circuit_images(qc, out_path):
    circuit_drawer(qc, output='mpl', filename=out_path)

def find_good_bitstrings(n, k, nqpa, full_nqpa, verbose=False):
    """Returns good bitstrings for circuit"""

    if verbose:
        print(f"Running find_good_bitstrings with n={n}, k={k}, nqpa={nqpa}, full_nqpa={full_nqpa}")

    if nqpa < n:
        if verbose:
            print("nqpa < n, returning empty list.")
        return []
    if n==0:
        q3 = '0'*k
        rest = list(product("01", repeat=k+full_nqpa))
        return [q3 + ''.join(bits) for bits in rest]
    good_bitstrings = []
    zero_result = ['0' * k]
    all_possible_bits = list(product("01", repeat=k))
    all_possible_bits_str = [''.join(bits) for bits in all_possible_bits]

    # Construct control bits
    unused_controls_list = list(product("01", repeat=full_nqpa - n))
    unused_controls_list_str = [''.join(bits) for bits in unused_controls_list]
    failed_control = [unused_controls + '1' + ('0' * (n-1)) for unused_controls in unused_controls_list_str] 
    success_control = [unused_controls + '0' + ('0' * (n-1)) for unused_controls in unused_controls_list_str]

    if verbose:
        print(f"failed_control: {failed_control}")
        print(f"success_control: {success_control}")

    if n % 2 == 1:
        failed_result_q3 = zero_result
        failed_result_q2 = all_possible_bits_str
        success_result_q3 = all_possible_bits_str
        success_result_q2 = zero_result
        if verbose:
            print("Odd n: using q3=0...0 for failed and q2=0...0 for success")
    else:
        failed_result_q3 = all_possible_bits_str
        failed_result_q2 = zero_result
        success_result_q3 = zero_result
        success_result_q2 = all_possible_bits_str
        if verbose:
            print("Even n: using q2=0...0 for failed and q3=0...0 for success")

    if verbose:
        print("Generating bitstrings for failed control case:")
    for q3 in failed_result_q3:
        for q2 in failed_result_q2:
            for control in failed_control:
                bitstring = q3 + q2 + control
                good_bitstrings.append(bitstring)
                if verbose:
                    print(f"  Added failed bitstring: {bitstring}")

    if n == nqpa:
        if verbose:
            print("n == nqpa, generating bitstrings for success control case:")
        for q3 in success_result_q3:
            for q2 in success_result_q2:
                for control in success_control:
                    bitstring = q3 + q2 + control
                    good_bitstrings.append(bitstring)
                    if verbose:
                        print(f"  Added success bitstring: {bitstring}")
    else:
        if verbose:
            print("n != nqpa, skipping success control case.")

    if verbose:
        print(f"Total good bitstrings found: {len(good_bitstrings)}")

    return good_bitstrings


def print_bitstrings(bitstrings, k):
    for b in bitstrings:
        q3 = b[:k]
        q2 = b[k:2*k]
        zpp = b[2*k]
        zp = b[2*k+1]
        z = b[2*k+2]
        print(f"q3={q3}, q2={q2}, z={z}, zp={zp}, zpp={zpp}")

    

def submit_pauli_job(qc_list, shots, sampler, backend,job_name='Three circuits QPA'):
    qc_transpiled_list = transpile(qc_list, backend=backend, optimization_level=3)
    return sampler.run(qc_transpiled_list, shots=shots)

def compute_fidelity(result, qc_list, accepted_bitstrings,shots):
    fid = 0
    for i in range(len(qc_list)):
        pub_result = result[i]
        counts = pub_result.data.control.get_counts()
        fidelity = sum(counts.get(bitstring, 0) for bitstring in accepted_bitstrings) / shots
        fid += fidelity
    return fid / len(qc_list)


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
    parser.add_argument('--nqpa', type=str, default='_ids', metavar='NQPA',
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
    total_shots = args.shots
    n_random = args.nrandom
    shots = round(total_shots/n_random)
    gatenoise = args.gatenoise
    aer_testing = args.aertesting
    fake_testing = args.faketesting
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    lambda_val = lambdas[args.lambda_index]
    # t0 = time.perf_counter()
    save_ids = False
    using_zero = True if ('0' in N_qpa ) else False
    if using_zero:
        print('Also finding nqpa=0 data')
    if '_ids' in N_qpa:
        assert aer_testing==False
        assert fake_testing==False
        save_ids = True
    else:
        N_qpa=int(N_qpa)
        purified_fidelity = [] 
        if using_zero:
            accepted_bitstrings0=find_good_bitstrings(0, k, N_qpa, 3, verbose=False)
        else:
            accepted_bitstrings1=find_good_bitstrings(1, k, N_qpa, 3, verbose=False)
            accepted_bitstrings2=find_good_bitstrings(2, k, N_qpa, 3, verbose=False)
            accepted_bitstrings3=find_good_bitstrings(3, k, N_qpa, 3, verbose=False)

    if using_zero:
        QPA0_list=[]
    if not using_zero or save_ids:
        QPA1_list = []
        QPA2_list = []
        QPA3_list = []
    for _ in range(n_random):
        if using_zero:
            QPA0= get_QPA_circuit_0(k, lambda_val)
            QPA0_list.append(QPA0)
        if not using_zero or save_ids:
            QPA1= get_QPA_circuit_1(k, lambda_val)
            QPA2= get_QPA_circuit_2(k, lambda_val)
            QPA3= get_QPA_circuit_3(k, lambda_val)
            QPA1_list.append(QPA1)
            QPA2_list.append(QPA2)
            QPA3_list.append(QPA3)
    if args.lambda_index==0:
        if using_zero:
            QPA0_for_draw = get_QPA_circuit_0(k, 0)
            circuit_path0 = args.output.replace(".csv","_0_original.png")
            circuit_drawer(QPA0_for_draw, output='mpl', filename=circuit_path0)
            print(f"[+] Saved original circuit0 to {circuit_path0}")
        if not using_zero or save_ids:
            QPA1_for_draw = get_QPA_circuit_1(k, 0)
            QPA2_for_draw = get_QPA_circuit_2(k, 0)
            QPA3_for_draw = get_QPA_circuit_3(k, 0)
            circuit_path1 = args.output.replace(".csv", "_1_original.png")
            circuit_path2 = args.output.replace(".csv", "_2_original.png")
            circuit_path3 = args.output.replace(".csv", "_3_original.png")
            circuit_drawer(QPA1_for_draw, output='mpl', filename=circuit_path1)
            circuit_drawer(QPA2_for_draw, output='mpl', filename=circuit_path2)
            circuit_drawer(QPA3_for_draw, output='mpl', filename=circuit_path3)
            print(f"[+] Saved original circuit1 to {circuit_path1}")
            print(f"[+] Saved original circuit2 to {circuit_path2}")
            print(f"[+] Saved original circuit3 to {circuit_path3}")
        
 
    
    
    
    

    if aer_testing:
        print('Using AER Sampler')
        backend = AerSimulator()
        noise_model = NoiseModel()
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 1), ['id_noisy', 'rx'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 2), ['rzz'])
        noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 3), ['cswap'])
        readout_error = ReadoutError([[1 - gatenoise, gatenoise], [gatenoise, 1 - gatenoise]])
        noise_model.add_all_qubit_readout_error(readout_error)
        sampler = AerSampler(options=dict(backend_options=dict(noise_model=noise_model)))
    elif fake_testing:
        print('Using FakeBackend Sampler')
        backend = FakeMarrakesh()
        sampler = SamplerV2(mode=backend)
    else:
        
        print('Using IBM Sampler')
        load_dotenv()
        token = os.getenv("IBM_QUANTUM_TOKEN")
        # service = QiskitRuntimeService(channel="ibm_quantum", instance='research-credits/100698/main', token=token)
        crn = os.getenv("CRN")
        service = QiskitRuntimeService(channel="ibm_cloud",token=token,instance=crn)
        backend = service.backend("ibm_marrakesh")
        sampler = SamplerV2(mode=backend)

    # ----- RUN -----
    if save_ids:
        print('Saving IDs instead of results')

        job1 = submit_pauli_job(QPA1_list, shots, sampler, backend,job_name=f'Circuit 1 Nqpa={N_qpa} at lambda={lambda_val}, nrandom={n_random}')
        
        job2 = submit_pauli_job(QPA2_list, shots, sampler, backend,job_name=f'Circuit 2 Nqpa={N_qpa} at lambda={lambda_val}, nrandom={n_random}')

        job3 = submit_pauli_job(QPA3_list, shots, sampler, backend,job_name=f'Circuit 3 Nqpa={N_qpa} at lambda={lambda_val}, nrandom={n_random}')

        # Submit jobs in series (safer for IBM backend)
        if using_zero:
            job0 = submit_pauli_job(QPA0_list, shots, sampler, backend,job_name=f'Circuit 0 Nqpa={N_qpa} at lambda={lambda_val}, nrandom={n_random}')
            # Extract job IDs
            job_ids = {
                "QPA0": job0.job_id(),
                "QPA1": job1.job_id(),
                "QPA2": job2.job_id(),
                "QPA3": job3.job_id()
            }
        else:
            job_ids = {
                "QPA1": job1.job_id(),
                "QPA2": job2.job_id(),
                "QPA3": job3.job_id()
            }

        print(f"Saved job IDs: {job_ids}")
        os.makedirs("data", exist_ok=True)
        if using_zero:
            df = pd.DataFrame({
                'lambda': [lambda_val],
                'jobid_QPA0': [job_ids['QPA0']],
                'jobid_QPA1': [job_ids['QPA1']],
                'jobid_QPA2': [job_ids['QPA2']],
                'jobid_QPA3': [job_ids['QPA3']]
            })
        else:
            df = pd.DataFrame({
                'lambda': [lambda_val],
                'jobid_QPA1': [job_ids['QPA1']],
                'jobid_QPA2': [job_ids['QPA2']],
                'jobid_QPA3': [job_ids['QPA3']]
            })

        output_path = args.output.replace('.csv', '_ids.csv')
        df.to_csv(output_path, index=False)
        print(f'[+] Job IDs saved to {output_path}')

    else:
        print('Running full jobs and getting fidelities')
        # Serial execution, compute fidelities directly
        if using_zero:
            result0 = submit_pauli_job(QPA0_list, shots, sampler, backend).result()
            fidelity0 = compute_fidelity(result0, QPA0_list, accepted_bitstrings0, shots)
            fidelity = fidelity0
        else:
            result1 = submit_pauli_job(QPA1_list, shots, sampler, backend).result()
            fidelity1 = compute_fidelity(result1, QPA1_list, accepted_bitstrings1, shots)

            result2 = submit_pauli_job(QPA2_list, shots, sampler, backend).result()
            fidelity2 = compute_fidelity(result2, QPA2_list, accepted_bitstrings2, shots)

            result3 = submit_pauli_job(QPA3_list, shots, sampler, backend).result()
            fidelity3 = compute_fidelity(result3, QPA3_list, accepted_bitstrings3, shots)

            fidelity = fidelity1 + fidelity2 + fidelity3
        purified_fidelity.append(fidelity)
        print(f"Purified fidelity: {fidelity}")

        os.makedirs("data", exist_ok=True)
        df = pd.DataFrame({
            'lambda': [lambda_val],
            f'QPA_{args.nqpa}': purified_fidelity
        })
        df.to_csv(args.output, index=False)
        print(f'[+] Fidelity output saved to {args.output}')
if __name__ == '__main__':
    main()