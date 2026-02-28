import argparse
import statistics
import random
from typing import Dict, Tuple, List

import numpy as np
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import (
    FakeBrisbane,
    FakeSherbrooke,
    FakeMarrakesh,
)


def _random_1q_clifford_circuit() -> QuantumCircuit:
    """Return a single-qubit random Clifford as a circuit.

    Tries qiskit.quantum_info.random_clifford; falls back to a small gate set
    approximating uniform mixing if not available.
    """
    try:
        from qiskit.quantum_info import random_clifford
        return random_clifford(1).to_circuit()
    except Exception:
        qc = QuantumCircuit(1)
        # Fallback set: I, X, Z, H, S, Sdg
        gate = random.choice(["i", "x", "z", "h", "s", "sdg"])
        if gate == "x":
            qc.x(0)
        elif gate == "z":
            qc.z(0)
        elif gate == "h":
            qc.h(0)
        elif gate == "s":
            qc.s(0)
        elif gate == "sdg":
            qc.sdg(0)
        # "i" does nothing
        return qc


def _random_2q_clifford_circuit() -> QuantumCircuit:
    """Return a two-qubit random Clifford as a circuit.

    Tries qiskit.quantum_info.random_clifford(2); falls back to a small gate set
    that mixes single-qubit and entangling gates.
    """
    try:
        from qiskit.quantum_info import random_clifford
        return random_clifford(2).to_circuit()
    except Exception:
        qc = QuantumCircuit(2)
        gate = random.choice([
            ("h", 0), ("h", 1), ("s", 0), ("s", 1), ("sdg", 0), ("sdg", 1),
            ("x", 0), ("x", 1), ("z", 0), ("z", 1),
            ("cx", 0, 1), ("cx", 1, 0), ("cz", 0, 1)
        ])
        if gate[0] == "h":
            qc.h(gate[1])
        elif gate[0] == "s":
            qc.s(gate[1])
        elif gate[0] == "sdg":
            qc.sdg(gate[1])
        elif gate[0] == "x":
            qc.x(gate[1])
        elif gate[0] == "z":
            qc.z(gate[1])
        elif gate[0] == "cx":
            qc.cx(gate[1], gate[2])
        elif gate[0] == "cz":
            try:
                qc.cz(gate[1], gate[2])
            except Exception:
                # Fallback CZ via H-CX-H
                qc.h(gate[2])
                qc.cx(gate[1], gate[2])
                qc.h(gate[2])
        return qc


def build_rb_circuit(m: int, preserve_sequence: bool = False, num_qubits: int = 1) -> QuantumCircuit:
    """Build a 1-qubit randomized benchmarking circuit of length m.

    Applies m random 1-qubit Clifford circuits, then the composite inverse,
    finally measures in Z basis. Ideal survival is returning to |0>.
    """
    qc = QuantumCircuit(num_qubits, num_qubits)
    seq: List[QuantumCircuit] = []
    # Apply m random Cliffords
    for _ in range(m):
        c = _random_1q_clifford_circuit() if num_qubits == 1 else _random_2q_clifford_circuit()
        seq.append(c)
        qc.compose(c, inplace=True)
        if preserve_sequence:
            qc.barrier()
    # Append the inverse of the composite
    inv = QuantumCircuit(num_qubits)
    for c in reversed(seq):
        inv.compose(c.inverse(), inplace=True)
    qc.compose(inv, inplace=True)
    # Measure
    qc.measure(list(range(num_qubits)), list(range(num_qubits)))
    return qc


def survival_prob_from_counts(counts: Dict[str, int], num_qubits: int = 1) -> float:
    """Return survival probability to |0...0> for a num_qubits measurement."""
    total = sum(counts.values()) or 1
    # Keys may be '0'/'1' or '0 ' with spaces depending on transpile; normalize
    p0 = 0.0
    for k, v in counts.items():
        key = k.replace(" ", "")
        target = "0" * num_qubits
        if key == target:
            p0 += v
    return p0 / total


def get_fake_backend(name: str):
    name = name.lower()
    if name in ("ibm_brisbane", "brisbane"):
        return FakeBrisbane()
    if name in ("ibm_sherbrooke", "sherbrooke"):
        return FakeSherbrooke()
    if name in ("ibm_marrakesh", "marrakesh"):
        return FakeMarrakesh()
    raise ValueError(f"Unknown fake backend '{name}'. Try ibm_brisbane, ibm_sherbrooke, ibm_marrakesh.")


def run_rb_trial(backend, shots: int, m: int, opt_level: int = 0, preserve_sequence: bool = False, num_qubits: int = 1) -> float:
    """Run one RB sequence of length m and return survival probability."""
    qc = build_rb_circuit(m, preserve_sequence=preserve_sequence, num_qubits=num_qubits)
    tqc = transpile(qc, backend=backend, optimization_level=opt_level)
    job = backend.run(tqc, shots=shots)
    result = job.result()
    counts = result.get_counts()
    if isinstance(counts, list):
        counts = counts[0]
    return survival_prob_from_counts(counts, num_qubits=num_qubits)


def main():
    parser = argparse.ArgumentParser(description="IBM Fake Backend Randomized Benchmarking (1q/2q/mixed)")
    parser.add_argument("--device", type=str, default="ibm_brisbane", help="Fake backend name: ibm_brisbane|ibm_sherbrooke|ibm_marrakesh")
    parser.add_argument("--shots", type=int, default=4000, help="Shots per sequence")
    parser.add_argument("--lengths", type=str, default="2,4,8,16,32", help="Comma-separated RB lengths (m)")
    parser.add_argument("--n-seqs", type=int, default=5, help="Random sequences per length")
    parser.add_argument("--rb-type", type=str, choices=["1q", "2q", "mixed"], default="mixed", help="Type of RB to run: 1-qubit, 2-qubit, or both.")
    parser.add_argument("--plot-circuit", type=str, default=None, help="Optional path to save a representative RB circuit plot (pre-transpile, PNG/text).")
    parser.add_argument("--plot-transpiled", type=str, default=None, help="Optional path to save the transpiled RB circuit plot (PNG/text).")
    parser.add_argument("--plot-output", type=str, choices=["mpl", "text"], default="mpl", help="Plot backend: 'mpl' to save PNG, 'text' to print ASCII")
    parser.add_argument("--print-circuit", action="store_true", help="Print RB circuit before and after transpilation (ASCII).")
    parser.add_argument("--opt-level", type=int, choices=[0, 1, 2, 3], default=0, help="Transpile optimization level (default 0 to avoid sequence cancellation).")
    parser.add_argument("--preserve-sequence", action="store_true", help="Insert barriers to prevent optimization from collapsing RB gates.")
    parser.add_argument("--plot-results", type=str, default=None, help="Optional path to save survival vs length plot (PNG).")
    parser.add_argument("--baseline", type=float, default=0.5, help="Baseline B for fit y = B + A * exp(-kappa * m). Default 0.5 for 1-qubit RB.")
    args = parser.parse_args()

    backend = get_fake_backend(args.device)
    # qiskit backends expose name as a property in newer versions
    try:
        backend_name = backend.name  # property
        if callable(backend_name):
            backend_name = backend_name()
    except Exception:
        backend_name = getattr(backend, "name", backend.__class__.__name__)
    print(f"Using fake backend: {backend_name}")

    # Parse lengths
    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]

    # Optional representative circuit (first length): print and/or plot
    if args.plot_circuit or args.plot_transpiled or args.print_circuit:
        num_q_example = 1 if args.rb_type == "1q" else 2
        qc_example = build_rb_circuit(lengths[0], preserve_sequence=args.preserve_sequence, num_qubits=num_q_example)
        # Print pre-transpile ASCII if requested
        if args.print_circuit:
            print("\n--- RB circuit (pre-transpile) ---")
            try:
                print(qc_example.draw(output="text"))
            except Exception:
                # Fallback to string repr
                print(qc_example)
        # Plot pre-transpile
        if args.plot_circuit:
            try:
                if args.plot_output == "mpl":
                    fig = qc_example.draw(output="mpl")
                    fig.savefig(args.plot_circuit, dpi=200, bbox_inches="tight")
                    print(f"Saved circuit plot to {args.plot_circuit}")
                else:
                    print("\n--- RB circuit (pre-transpile) ---")
                    print(qc_example.draw(output="text"))
            except Exception as e:
                print(f"Circuit plot failed: {e}. Falling back to text:")
                try:
                    print(qc_example.draw(output="text"))
                except Exception:
                    pass
        # Transpile
        try:
            tqc_example = transpile(qc_example, backend=backend, optimization_level=args.opt_level)
            # Print transpiled ASCII if requested
            if args.print_circuit:
                print("\n--- RB circuit (transpiled) ---")
                try:
                    print(tqc_example.draw(output="text"))
                except Exception:
                    print(tqc_example)
            # Plot transpiled
            if args.plot_transpiled:
                if args.plot_output == "mpl":
                    fig2 = tqc_example.draw(output="mpl")
                    fig2.savefig(args.plot_transpiled, dpi=200, bbox_inches="tight")
                    print(f"Saved transpiled circuit plot to {args.plot_transpiled}")
                else:
                    print("\n--- RB circuit (transpiled) ---")
                    print(tqc_example.draw(output="text"))
            elif args.plot_circuit and args.plot_output == "text":
                # If only pre-transpile path provided but text mode selected, also show transpiled text
                print("\n--- RB circuit (transpiled) ---")
                print(tqc_example.draw(output="text"))
        except Exception as e:
            print(f"Transpiled circuit plot failed: {e}")

    # Run RB across lengths for selected types
    summaries = {}
    types_to_run = [args.rb_type] if args.rb_type in ["1q", "2q"] else ["1q", "2q"]
    for rb_t in types_to_run:
        print(f"\n--- Running {rb_t} RB ---")
        num_qubits = 1 if rb_t == "1q" else 2
        summary = []  # (m, mean_survival, stdev)
        for m in lengths:
            survs = []
            for i in range(args.n_seqs):
                p0 = run_rb_trial(
                    backend,
                    shots=args.shots,
                    m=m,
                    opt_level=args.opt_level,
                    preserve_sequence=args.preserve_sequence,
                    num_qubits=num_qubits,
                )
                survs.append(p0)
                print(f"[{rb_t}] m={m} seq {i+1}/{args.n_seqs}: survival={p0:.4f}")
            mean_surv = statistics.mean(survs)
            stdev_surv = statistics.pstdev(survs) if len(survs) > 1 else 0.0
            summary.append((m, mean_surv, stdev_surv))
        summaries[rb_t] = summary

    # Print summary and a rough error per Clifford estimate
    print("\n=== RB Summary ===")
    print(f"Device: {backend_name}")
    print(f"Shots/sequence: {args.shots}, Sequences/length: {args.n_seqs}")
    for rb_t, summary in summaries.items():
        print(f"\n[{rb_t}]")
        for m, mu, sig in summary:
            print(f"m={m:>3} -> survival={mu:.4f} ± {sig:.4f}")

    # Fit y ≈ B + A * exp(-kappa * m) and optionally plot results
    try:
        for rb_t, summary in summaries.items():
            num_qubits = 1 if rb_t == "1q" else 2
            B_default = 0.5 if num_qubits == 1 else 0.25
            B = float(args.baseline) if args.rb_type in ["1q", "2q"] else B_default
            m_vals = np.array([m for m, _, _ in summary], dtype=float)
            y_vals = np.array([mu for _, mu, _ in summary], dtype=float)
            mask = y_vals > B + 1e-3
            if mask.sum() >= 2:
                m_adj = m_vals[mask]
                y_adj = np.log(y_vals[mask] - B)
                coeffs = np.polyfit(m_adj, y_adj, 1)
                slope, intercept = coeffs[0], coeffs[1]
                kappa = float(-slope)
                A = float(np.exp(intercept))
                p = float(np.exp(-kappa))
                lam = 1.0 - p  # depolarization strength per Clifford
                # Average gate infidelity per Clifford for d=2^n: r = (d-1)*(1-p)/d
                d = 2 ** num_qubits
                r = (d - 1) * (1.0 - p) / d
                print(f"\n[{rb_t}] Fit with B={B:.3f}:")
                print(f"A≈{A:.4f}, κ≈{kappa:.4f}, p≈{p:.4f}, λ≈{lam:.4f}, error/Clifford≈{r:.4f}")

                # Plot results if requested
                if args.plot_results:
                    try:
                        import matplotlib.pyplot as plt
                        plt.figure(figsize=(6,4))
                        plt.scatter(m_vals, y_vals, label="Survival", color="#1f77b4")
                        m_fit = np.linspace(float(m_vals.min()), float(m_vals.max()), 200)
                        y_fit = B + A * np.exp(-kappa * m_fit)
                        plt.plot(m_fit, y_fit, label=f"Fit (κ={kappa:.3f})", color="#ff7f0e")
                        plt.xlabel("Sequence length m")
                        plt.ylabel(f"Survival to |{'0'*num_qubits}>")
                        plt.title(f"{rb_t} RB on {backend_name}")
                        plt.legend()
                        plt.grid(True, alpha=0.3)
                        plt.tight_layout()
                        out_path = args.plot_results
                        if args.rb_type == "mixed" and out_path:
                            base, ext = out_path.rsplit('.', 1) if '.' in out_path else (out_path, 'png')
                            out_path = f"{base}_{rb_t}.{ext}"
                        plt.savefig(out_path, dpi=200)
                        print(f"Saved RB results plot to {out_path}")
                    except Exception as pe:
                        print(f"Plotting failed: {pe}")
            else:
                print(f"\n[{rb_t}] Insufficient spread above B≈{B:.3f} to fit; report survival table only.")
    except Exception as e:
        print(f"\nRB fit failed: {e}")


if __name__ == "__main__":
    main()
