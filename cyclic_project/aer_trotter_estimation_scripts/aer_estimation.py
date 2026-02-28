#!/usr/bin/env python3
"""
QPA + Trotterized Ising simulation with arbitrary inputs.
- Uses ising_class for Ising circuit
- Uses CircuitFactory/UnrolledStrategy for QPA circuit
- Uses original noise generation
"""
import numpy as np
import pandas as pd
from qiskit import transpile, QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit.quantum_info import Statevector
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError
from qiskit.circuit.library import RZZGate
from qiskit.visualization import circuit_drawer
import matplotlib.pyplot as plt
from scipy.linalg import expm

# Import QPA circuit logic
from core.circuit_factory import CircuitFactory
from core.strategies.unrolled import UnrolledStrategy
from core.noise_models import StandardDepolarizingStrategy, PauliTwirlingStrategy

# --- Ising class and exact statevector ---
class ising_class:
    def __init__(self, k, steps, t, J, h):
        self.k = k
        self.steps = steps
        self.t = t
        self.J = J
        self.h = h

    def get_trotterized_ising_circuit(self):
        dt = self.t / self.steps
        qc = QuantumCircuit(self.k)
        for _ in range(self.steps):
            # Even pairs
            for i in range(0, self.k - 1, 2):
                qc.append(RZZGate(-2 * self.J * dt), [i, i + 1])
            # Odd pairs
            for i in range(1, self.k - 1, 2):
                qc.append(RZZGate(-2 * self.J * dt), [i, i + 1])
            qc.barrier()
            # Transverse field
            for i in range(self.k):
                qc.rx(-2 * self.h * dt, i)
            qc.barrier()
        return qc

    def get_trotterized_ising_statevector(self):
        qc = self.get_trotterized_ising_circuit()
        qc.save_statevector()
        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def compute_exact_statevector(k, t, J, h):
    dim = 2**k
    I = np.eye(2)
    X = np.array([[0, 1], [1, 0]])
    Z = np.array([[1, 0], [0, -1]])
    def kron_n(*ops):
        out = ops[0]
        for op in ops[1:]:
            out = np.kron(out, op)
        return out
    H = np.zeros((dim, dim), dtype=complex)
    for q in range(k - 1):
        ops = [I] * k
        ops[q] = Z
        ops[q + 1] = Z
        H += -J * kron_n(*ops)
    for q in range(k):
        ops = [I] * k
        ops[q] = X
        H += -h * kron_n(*ops)
    psi0 = np.zeros(dim, dtype=complex)
    psi0[0] = 1.0

    U = expm(-1j * H * t)
    psi_final = U @ psi0
    return Statevector(psi_final)

# --- Main simulation stub ---
def main():
    import argparse, os
    from tqdm import tqdm

    parser = argparse.ArgumentParser(description="QPA + Trotterized Ising simulation with arbitrary inputs")
    parser.add_argument('--k', type=int, default=2, help='Number of qubits per register')
    parser.add_argument('--steps', type=int, default=10, help='Number of Trotter steps')
    # parser.add_argument('--steps-list', type=str, default='2,4,6,8,10,12,14,16,18,20', help='Comma-separated list of steps to sweep (fixes epsilon)')
    parser.add_argument('--steps-list', type=str, help='Comma-separated list of steps to sweep (fixes epsilon)')
    parser.add_argument('--t', type=float, default=1.0, help='Total evolution time')
    parser.add_argument('--J', type=float, default=1.0, help='Ising interaction strength')
    parser.add_argument('--h', type=float, default=1.0, help='Transverse field strength')
    parser.add_argument('--method', type=str, default='dynamic', choices=['unrolled','dynamic'], help='QPA circuit method')
    parser.add_argument('--n', type=int, default=3, help='Number of registers')
    parser.add_argument('--trials', type=int, default=3, help='Number of QPA rounds')
    parser.add_argument('--shots', type=int, default=20000, help='Number of shots')
    # compatibility single-epsilon
    parser.add_argument('--epsilon', type=float, default=None, help='Single depolarizing noise strength (if provided, overrides sweep)')
    # epsilon sweep args
    parser.add_argument('--epsilon-min', type=float, default=0.0, help='Minimum epsilon (noise strength)')
    parser.add_argument('--epsilon-max', type=float, default=0.001, help='Maximum epsilon (noise strength)')
    parser.add_argument('--epsilon-steps', type=int, default=11, help='Number of epsilon steps (inclusive)')
    parser.add_argument('--epsilon-index', type=int, default=None, help='Select single epsilon by index (overrides sweep)')
    parser.add_argument('--output', type=str, default='data/fidelity_vs_epsilon.csv', help='Output CSV file')
    parser.add_argument('--noise', type=str, default='depolarizing', choices=['depolarizing','twirling'], help='Noise model')
    parser.add_argument('--smoke-test', action='store_true', help='Show transpiled circuit and exit (no simulation)')
    args = parser.parse_args()

    from qiskit.quantum_info import SparsePauliOp

    # Build QPA strategy (strategy reused across sweep; build called per-eps below)
    strategy = CircuitFactory.create_strategy(args.method, args.k, args.trials, args.n)
    # noise_strategy = StandardDepolarizingStrategy(args.k) if args.noise == 'depolarizing' else PauliTwirlingStrategy(args.k)
    # strategy.set_noise_strategy(noise_strategy)

    # Determine mode and sweep values. If --steps-list provided, run steps-sweep
    # with a fixed epsilon; otherwise fix steps and sweep epsilon.
    if args.steps_list:
        steps_vals = [int(x) for x in args.steps_list.split(',') if x.strip()]
        epsilons = np.array([args.epsilon if args.epsilon is not None else args.epsilon_max])
        mode = 'steps'
    else:
        steps_vals = [args.steps]
        if args.epsilon is not None:
            epsilons = np.array([args.epsilon])
        else:
            epsilons = np.linspace(args.epsilon_min, args.epsilon_max, max(1, args.epsilon_steps))
            if args.epsilon_index is not None:
                epsilons = np.array([epsilons[args.epsilon_index]])
        mode = 'epsilon'

    from qiskit.quantum_info import SparsePauliOp

    # Containers for results
    if mode == 'steps':
        fidelities_steps = []
    else:
        fidelities = []

    # Unified nested loop: for each epsilon and each steps value build circuits,
    # pad projector, create noise model, and run estimator. This covers both
    # the steps-sweep (multiple steps, single epsilon) and epsilon-sweep
    # (single steps, multiple epsilons) cases.
    for eps in tqdm(epsilons, desc="ε sweep"):
        for s in steps_vals:
            # Build Ising and exact state for this steps value
            ising = ising_class(args.k, s, args.t, args.J, args.h)
            ising_circuit = ising.get_trotterized_ising_circuit()
            exact_state = ising.get_trotterized_ising_statevector()
            projector_op = SparsePauliOp.from_operator(exact_state.to_operator())

            # Build QPA strategy and circuit for this epsilon
            circuits_data = strategy.build(eps)
            qpa_circuit = circuits_data[0]['circuit'] if circuits_data else None

            # prepend Ising to every data register
            full_circuit = qpa_circuit.copy()
            data_regs = [reg for reg in full_circuit.qregs if reg.name.startswith('R')]
            for reg in data_regs:
                full_circuit.compose(ising_circuit, qubits=reg, inplace=True, front=True)

            # prepare padded projector acting on reserve register
            data_regs = [reg for reg in full_circuit.qregs if reg.name.startswith('R')]
            reserve_reg = data_regs[-1]
            reserve_indices = [full_circuit.find_bit(q).index for q in reserve_reg]
            total_qubits = full_circuit.num_qubits
            num_identity_left = min(reserve_indices)
            num_identity_right = total_qubits - max(reserve_indices) - 1

            identity_left = SparsePauliOp(["I" * num_identity_left]) if num_identity_left > 0 else None
            identity_right = SparsePauliOp(["I" * num_identity_right]) if num_identity_right > 0 else None

            if identity_left and identity_right:
                full_projector = identity_right.tensor(projector_op).tensor(identity_left)
            elif identity_left:
                full_projector = projector_op.tensor(identity_left)
            elif identity_right:
                full_projector = identity_right.tensor(projector_op)
            else:
                full_projector = projector_op

            # build noise model for this epsilon
            noise_model = NoiseModel()
            # helper to clamp depolarizing probability to a safe range
            def _safe_depolarizing(p, nq):
                p = float(p)
                # clamp to [0, 0.999999] to avoid library errors for extreme values
                p = max(0.0, min(p, 0.999999))
                return depolarizing_error(p, nq)

            # Scale noise roughly by gate size but keep probabilities within valid bounds
            p_rx = eps
            p_swap = min(eps * 2.0, 0.999999)
            p_rzz = min(eps * 10.0, 0.999999)
            p_cswap = min(eps * 20.0, 0.999999)
            p_init = eps

            noise_model.add_all_qubit_quantum_error(_safe_depolarizing(p_rx, 1), ['rx'])
            noise_model.add_all_qubit_quantum_error(_safe_depolarizing(p_swap, 2), ['swap'])
            # apply same two-qubit rzz-level error to rzz and swap gates
            noise_model.add_all_qubit_quantum_error(_safe_depolarizing(p_rzz, 2), ['rzz'])
            noise_model.add_all_qubit_quantum_error(_safe_depolarizing(p_cswap, 3), ['cswap'])
            # add single-qubit initialization/reset error
            noise_model.add_all_qubit_quantum_error(_safe_depolarizing(p_init, 1), ['initialize', 'reset'])
            readout_error = ReadoutError([[1 - eps, eps], [eps, 1 - eps]])
            noise_model.add_all_qubit_readout_error(readout_error)

            from qiskit_aer.primitives import EstimatorV2 as AerEstimator
            estimator = AerEstimator(options={
                'backend_options': {
                    'noise_model': noise_model,
                    'shots': args.shots
                }
            })

            # remove measurements that write into classical register named 'readout'
            readout_bits = set()
            for creg in full_circuit.cregs:
                if getattr(creg, "name", "") == "readout":
                    for cb in creg:
                        readout_bits.add(cb)

            full_circuit.data = [
                (inst, qargs, cargs)
                for inst, qargs, cargs in full_circuit.data
                if not (inst.name == 'measure' and any(cb in readout_bits for cb in cargs))
            ]

            result = estimator.run([(full_circuit, full_projector, None)]).result()
            fidelity = float(result[0].data.evs)

            if mode == 'steps':
                fidelities_steps.append(fidelity)
            else:
                fidelities.append(fidelity)

    # After sweep: write CSV according to mode
    def fmt(v):
        s = str(v)
        return s.replace('.', 'p')

    base_out = args.output
    if base_out.endswith('.csv'):
        base_root = base_out[:-4]
    else:
        base_root = base_out

    if mode == 'steps':
        # metadata: include fixed epsilon in filename
        eps_fixed = epsilons[0]
        meta_parts = [f"k{fmt(args.k)}", f"n{fmt(args.n)}", f"trials{fmt(args.trials)}", f"epsilon{fmt(eps_fixed)}"]
        out_path = f"{base_root}_stepsSweep_{'_'.join(str(s) for s in steps_vals)}_{'_'.join(meta_parts)}.csv"
        out_dir = os.path.dirname(out_path) or 'data'
        os.makedirs(out_dir, exist_ok=True)
        df_steps = pd.DataFrame({'steps': steps_vals, 'fidelity': fidelities_steps})
        df_steps.to_csv(out_path, index=False)
        print(f'[+] Steps-sweep CSV saved to {out_path}')
    else:
        # epsilon sweep CSV
        meta_keys = ['k', 'n', 'trials', 'steps', 't', 'J', 'h', 'method', 'noise', 'shots', 'epsilon_max']
        meta_parts = []
        for key in meta_keys:
            val = getattr(args, key)
            meta_parts.append(f"{key}{fmt(val)}")
        meta_suffix = '_'.join(meta_parts)
        out_path = f"{base_root}_{meta_suffix}.csv"
        out_dir = os.path.dirname(out_path) or 'data'
        os.makedirs(out_dir, exist_ok=True)
        df = pd.DataFrame({'epsilon': list(epsilons), 'fidelity': fidelities})
        df.to_csv(out_path, index=False)
        print(f'[+] Simple CSV saved to {out_path}')

    # Plot / save the final full_circuit (from last iteration)
    fig = circuit_drawer(full_circuit, output='mpl', scale=0.7, fold=30)
    plt.tight_layout()
    fig.savefig('qpa_circuit.pdf')
    print("[+] Saved QPA circuit plot as qpa_circuit.pdf")

if __name__ == '__main__':
    main()
