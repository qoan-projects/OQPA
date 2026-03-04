import os
from qiskit_ibm_runtime import QiskitRuntimeService

# Load .env from the same directory as this file
try:
    from dotenv import load_dotenv
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"))
except Exception as e:
    raise RuntimeError("python-dotenv not installed. Run: pip install python-dotenv") from e

token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBM_API")
if not token:
    raise RuntimeError("No IBM token found. Put IBM_QUANTUM_TOKEN=... (or IBM_API=...) in .env")

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    token=token
)

backs = service.backends()
print("num backends:", len(backs))
print("backend names:", [b.name for b in backs])

sim_backs = [b for b in backs if getattr(b, "simulator", False)]
print("simulators:", [b.name for b in sim_backs])

backend = sim_backs[0] if sim_backs else backs[0]
print("using:", backend.name, "is_simulator:", getattr(backend, "simulator", None))