import qnexus as qnx
import qnexus.exceptions as qnx_exc
from datetime import datetime

from pytket.circuit import Circuit
from pytket.circuit.display import render_circuit_jupyter

def main() -> None:
	qnx.login()

	project = qnx.projects.get_or_create(name="qpa-h2")
	qnx.context.set_active_project(project)
	config = qnx.QuantinuumConfig(device_name="H2-Emulator")

	# Retrieve an existing circuit from the Nexus database when available.
	try:
		existing_ref = qnx.circuits.get(name="GHZ-Circuit")
		render_circuit_jupyter(existing_ref.download_circuit())
	except qnx_exc.ZeroMatches:
		print("No existing circuit named 'GHZ-Circuit' found in the active scope.")

	# Build a new GHZ circuit locally.
	circuit = Circuit(10)
	circuit.H(0)
	for i, j in zip(circuit.qubits[:-1], circuit.qubits[1:]):
		circuit.CX(i, j)
	circuit.measure_all()

	render_circuit_jupyter(circuit)

	jobname_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
	ref = qnx.circuits.upload(circuit=circuit, name=f"GHZ-Circuit-{jobname_suffix}")

	render_circuit_jupyter(ref.download_circuit())

	ref_compile_job = qnx.start_compile_job(
		programs=[ref],
		backend_config=config,
		name=f"compile-job-{jobname_suffix}",
	)

	qnx.jobs.wait_for(ref_compile_job)
	compile_status = qnx.jobs.status(ref_compile_job)
	print(f"Compile job status: {compile_status}")

	compile_result = qnx.jobs.results(ref_compile_job)[0]
	ref_compiled_circuit = compile_result.get_output()

	ref_execute_job = qnx.start_execute_job(
		programs=[ref_compiled_circuit],
		n_shots=[100],
		backend_config=config,
		name=f"execution-job-{jobname_suffix}",
	)

	status = qnx.jobs.status(ref_execute_job)
	print(f"Execution job status: {status}")

	qnx.jobs.wait_for(ref_execute_job)
	ref_result = qnx.jobs.results(ref_execute_job)[0]
	backend_result = ref_result.download_result()

	print(backend_result.get_distribution())


if __name__ == "__main__":
	main()
