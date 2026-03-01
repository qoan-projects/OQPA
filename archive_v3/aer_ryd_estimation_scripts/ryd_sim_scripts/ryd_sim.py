import numpy as np
import argparse
import os
import csv
from scipy.linalg import expm
from tqdm import tqdm
import psutil

# ------------------ Helpers ------------------ #
def kron_n(op_list):
    out = op_list[0]
    for op in op_list[1:]:
        out = np.kron(out, op)
    return out

def build_single_site_op(n, op, site):
    I2 = np.eye(2, dtype=complex)
    return kron_n([op if i == site else I2 for i in range(n)])

def lindblad_super(L, d):
    return (np.kron(L, L.conj())
            - 0.5 * np.kron(np.eye(d), L.conj().T @ L)
            - 0.5 * np.kron((L.conj().T @ L).T, np.eye(d)))

# ------------------ Simulation ------------------ #
def run_simulation(k, V0, Omega_max, Delta_start, Delta_end, T_ramp_up, T_ramp_down, T_sweep, T2, num_steps, save_rho, outdir):
    d = 2**k
    T_total = T_ramp_up + T_sweep + T_ramp_down
    dt = T_total / num_steps
    t_grid = np.linspace(0, T_total, num_steps)
    gamma = 1.0 / T2

    # Pauli & Projector
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Pr = np.array([[0, 0], [0, 1]], dtype=complex)

    # Time profiles
    Omega_t = np.zeros_like(t_grid)
    Delta_t = np.zeros_like(t_grid)
    for idx, t in enumerate(t_grid):
        if t < T_ramp_up:
            Omega_t[idx] = Omega_max * (t / T_ramp_up)
            Delta_t[idx] = Delta_start
        elif t < T_ramp_up + T_sweep:
            Omega_t[idx] = Omega_max
            s = (t - T_ramp_up) / T_sweep
            Delta_t[idx] = Delta_start + (Delta_end - Delta_start) * s
        else:
            Omega_t[idx] = Omega_max * (1 - (t - T_ramp_up - T_sweep) / T_ramp_down)
            Delta_t[idx] = Delta_end

    # Operators
    X_ops = [build_single_site_op(k, X, j) for j in range(k)]
    Pr_ops = [build_single_site_op(k, Pr, j) for j in range(k)]

    # Initial state |000...0⟩
    rho = np.zeros((d, d), dtype=complex)
    rho[0, 0] = 1.0
    rho_vec = rho.flatten()

    # Decoherence Liouvillian
    L_jump_total = sum(lindblad_super(np.sqrt(2*gamma) * Pr_ops[j], d) for j in range(k))

    # Time evolution
    for idx in tqdm(range(num_steps), desc="Simulating", unit="step"):
        H_drive = sum(Omega_t[idx]/2 * X_ops[j] for j in range(k))
        H_det = sum(-Delta_t[idx] * Pr_ops[j] for j in range(k))
        H_int = sum(V0 * Pr_ops[i] @ Pr_ops[(i+1) % k] for i in range(k))
        H_t = H_drive + H_det + H_int

        L_coherent = -1j * (np.kron(H_t, np.eye(d)) - np.kron(np.eye(d), H_t.T))
        L_total = L_coherent + L_jump_total
        U = expm(L_total * dt)
        rho_vec = U @ rho_vec

    # Final state
    rho_final = rho_vec.reshape((d, d))

    # Fidelity with target (|1010⟩ + |0101⟩)/√2
    basis_1010 = np.zeros((d,), dtype=complex)
    basis_0101 = np.zeros((d,), dtype=complex)
    basis_1010[int('1010', 2)] = 1.0
    basis_0101[int('0101', 2)] = 1.0
    psi_target = (basis_1010 + basis_0101) / np.sqrt(2)
    fidelity = np.real(psi_target.conj().T @ rho_final @ psi_target)

    # Construct filename suffix with key parameters
    suffix = (
        f"k{k}_"
        f"V{V0 / (2 * np.pi * 1e6):.4g}_"
        f"Om{Omega_max / (2 * np.pi * 1e6):.4g}_"
        f"Del{Delta_start / (2 * np.pi * 1e6):.4g}to{Delta_end / (2 * np.pi * 1e6):.4g}_"
        f"ramp{T_ramp_up / 1e-6:.4g}_{T_sweep / 1e-6:.4g}_{T_ramp_down / 1e-6:.4g}_"
        f"T{T2 * 1e6:.4g}"
    )

    # Save fidelity as CSV
    fidelity_dir = f"../data/{outdir}"
    os.makedirs(fidelity_dir, exist_ok=True)
    fidelity_filename = f"{fidelity_dir}/fidelity_{suffix}.csv"
    with open(fidelity_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["k", "V0", "Omega_max", "Delta_start", "T_ramp_up", "T_sweep", "T_ramp_down", "fidelity"])
        writer.writerow([k, V0, Omega_max, Delta_start, T_ramp_up, T_sweep, T_ramp_down, fidelity])

    # Save final density matrix if requested
    if save_rho:
        rho_dir = f"../data/rho_{outdir}"
        os.makedirs(rho_dir, exist_ok=True)
        rho_filename = f"{rho_dir}/rho_{suffix}.npy"
        np.save(rho_filename, rho_final)



# ------------------ CLI ------------------ #
if __name__ == "__main__":
    # print("Python PID:", os.getpid())
    # print("CPU Count:", psutil.cpu_count(logical=True))
    # print("CPU Affinity:", psutil.Process().cpu_affinity())
    # print("CPU Usage:", psutil.cpu_percent(interval=1, percpu=True))

    parser = argparse.ArgumentParser(description="Rydberg fidelity simulator")
    parser.add_argument("--Omega_max", type=float, default=3)
    parser.add_argument("--Delta_start", type=float, default=-4)
    parser.add_argument("--Delta_end", type=float, default=4)
    parser.add_argument("--T_ramp_up", type=float, default=0.33)
    parser.add_argument("--T_ramp_down", type=float, default=0.33)
    parser.add_argument("--T_sweep", type=float, default=0.34)
    parser.add_argument("--V0", type=float, default=40)
    parser.add_argument("--T2", type=float, default=6)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--num_steps", type=int, default=1000)
    parser.add_argument("--save-rho", action="store_true")
    parser.add_argument("--outdir", type=str, default="fidelity", help="Output subdirectory name")

    args = parser.parse_args()
    run_simulation(
        k=args.k,
        V0=args.V0 * 2 * np.pi * 1e6,
        Omega_max=args.Omega_max * 2 * np.pi * 1e6,
        Delta_start=args.Delta_start * 2 * np.pi * 1e6,
        Delta_end=args.Delta_end * 2 * np.pi * 1e6,
        T_ramp_up=args.T_ramp_up * 1e-6,
        T_ramp_down=args.T_ramp_down * 1e-6,
        T_sweep=args.T_sweep * 1e-6,
        T2=args.T2 * 1e-6,
        num_steps=args.num_steps,
        save_rho=args.save_rho,
        outdir=args.outdir
    )