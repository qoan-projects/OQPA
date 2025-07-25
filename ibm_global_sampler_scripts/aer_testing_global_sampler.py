import numpy as np
from qiskit import QuantumCircuit,transpile, ClassicalRegister, QuantumRegister
from qiskit.quantum_info import Kraus, SuperOp
from qiskit.visualization import plot_histogram
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.quantum_info import Statevector,DensityMatrix,state_fidelity,partial_trace, Operator
from matplotlib import pyplot as plt
from functools import reduce
from scipy.linalg import expm
import pandas as pd
from qiskit_aer import AerSimulator
import qiskit.circuit.classical as qiskit_classical
from IPython.display import display
#from qiskit.opflow import I, Z, StateFn, PauliExpectation, CircuitSampler
#from qiskit import Aer, execute, transpile
from qiskit_aer.primitives import SamplerV2 as AerSampler
# Import from Qiskit Aer noise module
from qiskit_aer.noise import (
    NoiseModel,
    QuantumError,
    ReadoutError,
    depolarizing_error,
    pauli_error,
    thermal_relaxation_error,
)
import argparse
from tqdm import tqdm
import time
import os
from qiskit.visualization import circuit_drawer
def get_QPA_circuit(k: int,
                    n_qpa: int,
                    LAMBDA: float,
                    test_depolarization: bool = False) -> QuantumCircuit:
    """
    Build a “do-nothing” circuit, optionally sprinkle manual depolarising
    noise, then append `n_qpa` rounds of the QPA purification net.

    Parameters
    ----------
    k : int
        Number of data qubits per register (→ total qubits = 4·k).
    n_qpa : int
        How many recursive QPA rounds to apply.
    LAMBDA : float
        Probability to apply a random single-qubit Pauli if
        `test_depolarization` is True.
    test_depolarization : bool
        If True, insert an X/Y/Z gate with probability `eps`
        on every qubit *before* the QPA network.
    """

    # Classical and quantum registers
    creg = ClassicalRegister(k, "control")
    qreg = QuantumRegister(4 * k, "q")
    qc = QuantumCircuit(qreg, creg)

    # ------------------------------------------------------------------
    # 1) Kruass decomposition of depolarisation
    # ------------------------------------------------------------------
    if test_depolarization:
        rng = np.random.default_rng()

        reg_ranges = [range(k, 2 * k), range(2 * k, 3 * k), range(3 * k, 4 * k)]
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
                    # identity = do nothing for 'i'

    # ------------------------------------------------------------------
    # 2) QPA SWAPNET (recursive)
    # ------------------------------------------------------------------
    def _recursive(level: int, circ: QuantumCircuit) -> QuantumCircuit:
        """Attach one level of the SWAP-net and recurse if needed."""
        # 2a. Prepare GHZ (or |+⟩ if d == 1)
        for i in range(k):
            circ.reset(i)
        circ.h(0)
        for i in range(1, k):
            circ.cx(0, i)

        # 2b. Controlled SWAP between reg-1 and reg-2
        for i in range(k):
            circ.cswap(i, i + k, i + 2 * k)

        # 2c. Hadamards again + parity measurement
        for i in range(k):
            circ.h(i)
        parity = qiskit_classical.expr.lift(creg[0])
        for i in range(k):
            circ.measure(i, creg[i])
            if i:
                parity = qiskit_classical.expr.bit_xor(parity, creg[i])

        # 2d. Conditional branch
        with circ.if_test(parity) as _else:
            pass
        with _else:
            # swap reg-2 ↔ reg-3
            for i in range(k):
                circ.swap(i + 2 * k, i + 3 * k)
            # Recurse if more levels requested
            if level > 1:
                _recursive(level - 1, circ)

        return circ

    qc = _recursive(n_qpa, qc) if n_qpa else qc

    # ------------------------------------------------------------------
    # 3) Final measurement of the last register if needed
    # ------------------------------------------------------------------
    for i in range(k):
        qc.measure(3 * k + i, creg[i])

    return qc


def run_qc_and_return_state(qc):

    # Select Aer Simulator backend
    simulator = AerSimulator()

    def execute_circuit_on_state(qc):
        """ Executes a circuit on the AerSimulator and returns the state result. """
        qc_transpiled = transpile(qc, simulator)
        result = simulator.run(qc_transpiled).result()
        return result.get_statevector(qc_transpiled)

    qc.save_statevector()
    state = execute_circuit_on_state(qc)

    return state

def sample_qc_and_return_distribution(qc,shots=1024,sampler = AerSampler()):
    #RUN THE CIRCUIT AND MEASURE CLASSICALLY THE STATE IN REGISTER Q3, SHOULD RETURN A SEQUENCE OF BITS OF d DIMENSIONS FOR EACH SHOT, REPRESENTING THE FINAL STATE MEASURED
    pass_manager = generate_preset_pass_manager(3, AerSimulator())
    isa_circuit = pass_manager.run(qc)
    qc_transpiled = transpile(isa_circuit)
    result = sampler.run([qc_transpiled],shots=shots).result()
    pub_result = result[0]
    counts = pub_result.data.control.get_counts()
    return counts

def get_fidelity_from_paulis(qc_list, shots,k,sampler = AerSampler()):
    #RUN THE CIRCUIT AND MEASURE CLASSICALLY THE STATE IN REGISTER Q3, SHOULD RETURN A SEQUENCE OF BITS OF d DIMENSIONS FOR EACH SHOT, REPRESENTING THE FINAL STATE MEASURED
    pass_manager = generate_preset_pass_manager(3, AerSimulator())
    isa_circuit_list = pass_manager.run(qc_list)
    qc_transpiled_list = transpile(isa_circuit_list)
    result = sampler.run(qc_transpiled_list,shots=shots).result()
    fid=0
    for i in range(len(qc_list)):
        pub_result = result[i]
        counts = pub_result.data.control.get_counts()
        fidelity = counts['0'*k]/shots
        fid+=fidelity
    fid=fid/len(qc_list)
    return fid



# Run the function
def main():
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
    parser.add_argument('--output', type=str, default='data/fidelity_vs_lambda.csv', metavar='OUTPUT',
                        help='Path to output CSV file (default: data/fidelity_vs_lambda.csv)')
    args = parser.parse_args()
    k = args.k
    N_qpa = args.nqpa
    total_shots = args.shots
    n_random = args.nrandom
    shots = round(total_shots/n_random)
    gatenoise = args.gatenoise
    lambdas = np.linspace(args.lambda_min, args.lambda_max, args.lambda_steps)
    if args.lambda_index is not None:
        lambdas = [lambdas[args.lambda_index]]

    purified_fidelity = []
    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 1), ['id_noisy', 'rx'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 2), ['rzz'])
    noise_model.add_all_qubit_quantum_error(depolarizing_error(gatenoise, 3), ['cswap'])
    readout_error = ReadoutError([[1 - gatenoise, gatenoise], [gatenoise, 1 - gatenoise]])
    noise_model.add_all_qubit_readout_error(readout_error)
    for lambda_val in tqdm(lambdas, desc="Sweeping over λ", unit="λ"):
        # t0 = time.perf_counter()
        QPA_list = []
        for _ in range(n_random):
            QPA = get_QPA_circuit(k, N_qpa, lambda_val, test_depolarization=True)
            QPA_list.append(QPA)
        if args.lambda_index==0:
            QPA0 = get_QPA_circuit(k, N_qpa, 0, test_depolarization=True)
            circuit_path = args.output.replace(".csv", "_original.png")
            circuit_drawer(QPA0, output='mpl', filename=circuit_path)
            print(f"[+] Saved original circuit to {circuit_path}")
            
        
        sampler = AerSampler(options=dict(backend_options=dict(noise_model=noise_model)))
        fidelity = get_fidelity_from_paulis(QPA_list, shots,k,sampler=sampler)
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


