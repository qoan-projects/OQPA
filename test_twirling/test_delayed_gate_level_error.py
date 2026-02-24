import os
import numpy as np
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
from qiskit_experiments.library import ProcessTomography
from qiskit.quantum_info import PTM, Operator, random_clifford


# ----------------------------
# 1. Base circuit: just an idle delay (plus barriers)
# ----------------------------
def delayed_gate_level_error_circuit(delay_dt, num_qubits):
    """
    Circuit whose *intended* action is identity, with explicit idle delays.
    delay_dt is in backend 'dt' ticks.
    """
    qc = QuantumCircuit(num_qubits)
    qc.barrier()
    for q in range(num_qubits):
        qc.delay(int(delay_dt), q, unit="dt")
    qc.barrier()
    qc.name = "idle_delay"
    return qc


# ----------------------------
# 2. Clifford twirl: C -> circuit -> C†
# ----------------------------
def apply_random_clifford(qc, rng, undo=True):
    """
    Returns:  C ∘ qc ∘ C†  if undo=True
    """
    n = qc.num_qubits
    seed = int(rng.integers(0, 2**32 - 1))
    C = random_clifford(n, seed=seed)

    out = C.to_circuit().compose(qc)
    if undo:
        out = out.compose(C.adjoint().to_circuit())

    out.name = f"clifford_twirled_undo{int(undo)}"
    return out


# ----------------------------
# 3. Process tomography -> PTM
# ----------------------------
def ptm_from_process_tomography(circuit, backend):
    pt = ProcessTomography(circuit)

    # IMPORTANT: disable scheduling passes (they choke on unscheduled delay circuits)
    exp_data = pt.run(
        backend=backend,
        transpile_options={
            "scheduling_method": None,   # avoids ConstrainedReschedule path
        },
    )
    exp_data.block_for_results()

    # avoid deprecation warning by using dataframe=True
    df = exp_data.analysis_results(dataframe=True)
    choi = df.loc[df["name"] == "state", "value"].iloc[0]
    return PTM(choi).data


# ----------------------------
# 4. Plot PTM heatmap
# ----------------------------
PAULIS_2Q = [
    "II", "IX", "IY", "IZ",
    "XI", "XX", "XY", "XZ",
    "YI", "YX", "YY", "YZ",
    "ZI", "ZX", "ZY", "ZZ",
]

def plot_ptm(matrix, title, path):
    mat = np.real(matrix)
    plt.figure(figsize=(9, 9))
    plt.imshow(mat, interpolation="nearest")
    plt.xticks(range(mat.shape[1]), PAULIS_2Q[: mat.shape[1]], rotation=90)
    plt.yticks(range(mat.shape[0]), PAULIS_2Q[: mat.shape[0]])
    plt.title(title)
    plt.colorbar(fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()


# ----------------------------
# 5. Main
# ----------------------------
if __name__ == "__main__":
    backend = FakeSherbrooke()

    num_qubits = 2
    delay_dt = 4000        # change this to sweep idle time
    num_randomizations = 1   # start small; tomography is expensive
    undo = True

    base = delayed_gate_level_error_circuit(delay_dt=delay_dt, num_qubits=num_qubits)

    rng = np.random.default_rng(0)
    twirled_circuits = [apply_random_clifford(base, rng, undo=undo) for _ in range(num_randomizations)]

    ptms = [ptm_from_process_tomography(c, backend) for c in twirled_circuits]
    ptm_avg = np.mean(ptms, axis=0)

    # For an idle circuit, the *ideal* is identity channel, so ptm_ideal = I.
    # Still, keep this in case you later change base to include unitaries.
    ptm_ideal = PTM(Operator(base)).data
    ptm_ideal_inv = np.linalg.pinv(ptm_ideal)  # more stable than inv
    ptm_noise_avg = ptm_avg @ ptm_ideal_inv

    off_diag = np.linalg.norm(ptm_noise_avg - np.diag(np.diag(ptm_noise_avg)))

    print("Averaged PTM (includes whatever the circuit does + noise):")
    print(np.round(ptm_avg, 3))
    print("\nAveraged effective noise PTM:")
    print(np.round(ptm_noise_avg, 3))
    print("\nOff diagonal Frobenius norm (noise):", off_diag)

    # ----------------------------
    # Save outputs
    # ----------------------------
    output_dir = os.path.dirname(os.path.abspath(__file__))

    # save a transpiled representative circuit (base)
    base_transpiled = transpile(base, backend, optimization_level=0)

    fig = twirled_circuits[0].draw("mpl")
    fig.savefig(os.path.join(output_dir, "transpiled_base_circuit.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)

    with open(os.path.join(output_dir, "transpiled_base_circuit.txt"), "w") as f:
        f.write(base_transpiled.draw("text").single_string())

    np.save(os.path.join(output_dir, "ptm_avg.npy"), ptm_avg)
    np.save(os.path.join(output_dir, "ptm_noise_avg.npy"), ptm_noise_avg)

    np.savetxt(os.path.join(output_dir, "ptm_avg.csv"), np.real(ptm_avg), delimiter=",")
    np.savetxt(os.path.join(output_dir, "ptm_noise_avg.csv"), np.real(ptm_noise_avg), delimiter=",")

    plot_ptm(ptm_avg, "Averaged PTM (Real Part)", os.path.join(output_dir, "ptm_avg.png"))
    plot_ptm(ptm_noise_avg, "Averaged Effective Noise PTM (Real Part)", os.path.join(output_dir, "ptm_noise_avg.png"))

    print("\nSaved files to:", output_dir)