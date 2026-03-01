import os
import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService

# Try the modern Sampler first, fall back if your install is older
try:
    from qiskit_ibm_runtime import SamplerV2 as Sampler
except Exception:
    from qiskit_ibm_runtime import Sampler


def load_token():
    try:
        from dotenv import load_dotenv
        here = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(here, ".env"))
    except Exception:
        pass

    token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBM_API")
    if not token:
        raise RuntimeError("Set IBM_QUANTUM_TOKEN or IBM_API in env or .env")
    return token


def build_one_circuit(pauli_label: str) -> QuantumCircuit:
    qc = QuantumCircuit(1, 1)
    qc.reset(0)

    if pauli_label == "X":
        qc.x(0)
    elif pauli_label == "Y":
        qc.y(0)
    elif pauli_label == "Z":
        qc.z(0)
    # "I" does nothing

    qc.measure(0, 0)
    return qc


def decode_sampler_result_to_bits(result, N: int):
    """
    Returns a length N numpy array of bits in {0,1}.

    Handles common Sampler result formats by extracting the most likely outcome.
    With shots=1, it will essentially be the observed outcome.
    """
    bits = np.zeros(N, dtype=np.int8)

    # Sampler V1 style: result.quasi_dists is a list of QuasiDistribution
    if hasattr(result, "quasi_dists"):
        qds = result.quasi_dists
        for i, qd in enumerate(qds):
            outcome_int = max(qd.items(), key=lambda kv: kv[1])[0]
            bits[i] = int(outcome_int) & 1
        return bits

    # Sampler V2 style: result is iterable of per circuit objects
    for i in range(N):
        r = result[i]

        # Some V2 results expose a measurement container with counts
        if hasattr(r, "data") and hasattr(r.data, "meas"):
            counts = r.data.meas.get_counts()
            bitstr = max(counts.items(), key=lambda kv: kv[1])[0]
            bits[i] = int(bitstr[-1])
            continue

        # Some expose quasi distributions per item
        if hasattr(r, "quasi_dists"):
            qd = r.quasi_dists[0] if isinstance(r.quasi_dists, (list, tuple)) else r.quasi_dists
            outcome_int = max(qd.items(), key=lambda kv: kv[1])[0]
            bits[i] = int(outcome_int) & 1
            continue

        raise RuntimeError(f"Unknown result format at index {i}: {type(r)}")

    return bits


def main():
    lam = 0.1
    N = 4000
    shots = 1
    seed = 0

    rng = np.random.default_rng(seed)

    token = load_token()
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
    backend = service.backend("ibm_marrakesh")
    print("backend:", backend.name)

    labels = np.array(["I", "X", "Y", "Z"], dtype=object)
    probs = np.array([1.0 - 3.0 * lam / 4.0, lam / 4.0, lam / 4.0, lam / 4.0], dtype=float)
    choices = rng.choice(labels, size=N, p=probs)

    circuits = [build_one_circuit(c) for c in choices]
    circuits_t = transpile(circuits, backend=backend, optimization_level=0)

    sampler = Sampler(backend)
    job = sampler.run(circuits_t, shots=shots)

    print("job id:", job.job_id())
    print("status:", job.status())

    result = job.result()
    bits = decode_sampler_result_to_bits(result, N)

    n1 = int(bits.sum())
    n0 = int(bits.size - n1)
    p1 = n1 / bits.size

    # For this test: start |0>, apply I/X/Y/Z, measure Z
    # Ideal P(1) = P(X or Y) = lam/2 under your convention A
    lam_hat = 2.0 * p1

    print("N:", bits.size, "shots:", shots)
    print("counts:", {"0": n0, "1": n1})
    print("p(1):", round(p1, 6))
    print("lambda_hat:", round(lam_hat, 6))
    print("first 20 choices:", choices[:20].tolist())
    print("first 20 bits:", bits[:20].tolist())


if __name__ == "__main__":
    main()