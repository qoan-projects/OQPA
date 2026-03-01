import os
import numpy as np
from qiskit_ibm_runtime import QiskitRuntimeService

JOB_ID = "d6cbv1ng4t5c7385cb40"

# Load token from .env next to this script (optional)
try:
    from dotenv import load_dotenv
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"))
except Exception:
    pass

token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBM_API")
if not token:
    raise RuntimeError("Set IBM_QUANTUM_TOKEN (or IBM_API) in your env or .env")

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    token=token,
    # instance="QC1",  # only include if you have a saved account for it; otherwise omit
)

job = service.job(JOB_ID)
print("backend:", job.backend().name)
print("status:", job.status())

res = job.result()
item0 = list(res)[0]  # dict

# raw measured bits: shape (N, 1, 1) usually
raw_c = np.asarray(item0["c"]).reshape(-1).astype(np.int8)

# samplomatic's flip bookkeeping for that classical register
# (same shape as c)
raw_flip = np.asarray(item0.get("measurement_flips.c")).reshape(-1).astype(np.int8)

if raw_flip.size != raw_c.size:
    raise RuntimeError(f"Size mismatch: c has {raw_c.size} bits but measurement_flips.c has {raw_flip.size}")

# decoded bit in the standard Z basis
decoded = raw_c ^ raw_flip

N = decoded.size
n1 = int(decoded.sum())
n0 = N - n1
p1 = n1 / N

# For your circuit (|0> then id then measure Z), depol gives P(1)=lambda/3 ideally.
lam_hat = 3.0 * p1

print("N:", N)
print("raw counts:", {"0": int((1 - raw_c).sum()), "1": int(raw_c.sum())})
print("flip counts:", {"0": int((1 - raw_flip).sum()), "1": int(raw_flip.sum())})
print("decoded counts:", {"0": n0, "1": n1})
print("p_decoded(1):", p1)
print("lambda_hat (assuming ideal baseline):", lam_hat)

print("first 20 raw c:", raw_c[:20].tolist())
print("first 20 flips:", raw_flip[:20].tolist())
print("first 20 decoded:", decoded[:20].tolist())