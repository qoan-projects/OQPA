import os
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import PauliLindbladMap
from samplomatic import InjectNoise, build
import matplotlib.pyplot as plt

# Twirl class name can differ across samplomatic versions
try:
    from samplomatic import Twirl
except Exception:
    from samplomatic import TwirlPaulis as Twirl

# Load token from .env if present
try:
    from dotenv import load_dotenv
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"))
except Exception:
    pass

from qiskit_ibm_runtime import QiskitRuntimeService, Executor
try:
    # Newer clients
    from qiskit_ibm_runtime import QuantumProgram
except Exception:
    # Some versions expose it here
    from qiskit_ibm_runtime.quantum_program import QuantumProgram


def depol_map_from_lambda(lam: float) -> PauliLindbladMap:
    """
    Single-qubit depolarizing channel:
      E_lam(rho) = (1-lam) rho + (lam/3)(X rho X + Y rho Y + Z rho Z)
    Parameterized via equal Pauli Lindblad rates.
    Valid for 0 <= lam < 3/4.
    """
    if not (0.0 <= lam < 0.75):
        raise ValueError("lambda must satisfy 0 <= lambda < 3/4")
    r = -0.25 * np.log(1.0 - (4.0 * lam / 3.0))
    return PauliLindbladMap.from_list([("X", r), ("Y", r), ("Z", r)])


# -----------------------------
# 1) Build a tiny circuit
# -----------------------------
qc = QuantumCircuit(1, 1)

# InjectNoise requires Twirl around it
with qc.box([Twirl(), InjectNoise(ref="depol")]):
    qc.id(0)

# Measurement also needs Twirl box for samplomatic propagation rules
with qc.box([Twirl()]):
    qc.measure(0, 0)

# Build template + samplex (do NOT add extra measure after build)
template, samplex = build(qc)

# -----------------------------
# 2) Bind your noise map
# -----------------------------
lam = 0.05
depol = depol_map_from_lambda(lam)

inputs = samplex.inputs()
print(inputs)

sx_in = inputs.bind()
# Your printed interface showed this key
sx_in["pauli_lindblad_maps.depol"] = depol

# -----------------------------
# 3) Runtime service
# -----------------------------
token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBM_API")
if not token:
    raise RuntimeError("Set IBM_QUANTUM_TOKEN or IBM_API in env or .env")

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    token=token,
)

# --- choose backend (avoid miami for now) ---
backend = service.least_busy(operational=True, simulator=False)
if backend.name == "ibm_miami":
    # pick next least busy non-miami
    candidates = [b for b in service.backends(operational=True) if b.name != "ibm_miami"]
    backend = min(candidates, key=lambda b: b.status().pending_jobs)

print("Using backend:", backend.name, "pending_jobs:", backend.status().pending_jobs)

# --- cheapest smoke test ---
shots = 1
program = QuantumProgram(shots=shots)
program.append_samplex_item(
    circuit=template,
    samplex=samplex,
    samplex_arguments=dict(sx_in),
    shape=(200,),          # 1 randomization
)

fig1 = qc.draw("mpl")
fig1.show()

fig2 = template.draw("mpl")
fig2.show()

plt.show() 

# # --- Executor API for your build: pass backend positionally ---
# executor = Executor(backend)     # not Executor(backend=backend)
# job = executor.run(program)

# print("job id:", job.job_id())
# print("job status:", job.status())

# result = job.result()
# print("final status:", job.status())
# print(result)