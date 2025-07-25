from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService()
backends = service.backends(simulator=False, operational=True)
for b in backends:
    props = b.properties()
    # Example: get average two-qubit gate error
    errors = [inst for inst in props.qubit_property(1).get("readout_error", [])]
    print(b.name, "qubits:", b.num_qubits, "2Q errors sample:", errors[:3])