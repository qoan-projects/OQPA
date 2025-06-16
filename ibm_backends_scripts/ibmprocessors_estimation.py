import numpy as np
from qiskit import QuantumCircuit,transpile, ClassicalRegister, QuantumRegister
from qiskit.quantum_info import Kraus, SuperOp
from qiskit.visualization import plot_histogram
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.quantum_info import Statevector,DensityMatrix,state_fidelity,partial_trace, Operator
from matplotlib import pyplot as plt
from functools import reduce
from scipy.linalg import expm
import pandas as pd
from qiskit_aer import AerSimulator
import qiskit.circuit.classical as qiskit_classical
from qiskit.quantum_info import SparsePauliOp
from IPython.display import display
from qiskit.providers.fake_provider import GenericBackendV2
#from qiskit.opflow import I, Z, StateFn, PauliExpectation, CircuitSampler
#from qiskit import Aer, execute, transpile
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
import os
from qiskit_ibm_runtime import QiskitRuntimeService, EstimatorV2
from dotenv import load_dotenv
# Import from Qiskit Aer noise module
from qiskit_aer.noise import (
    NoiseModel,
    QuantumError,
    ReadoutError,
    depolarizing_error,
    pauli_error,
    thermal_relaxation_error,
)
from qiskit_ibm_runtime import QiskitRuntimeService
load_dotenv()  # Load from .env file
token = os.getenv("IBM_QUANTUM_TOKEN")
### SET ACCOUNT IF NEEDED -----------------------------------
# QiskitRuntimeService.save_account(
#     token=token, channel="ibm_quantum", overwrite=True
# )

# service = QiskitRuntimeService()
# backends = service.backends(dynamic_circuits=True)

# for backend in backends:
#     print(backend.name)
# quit()
class ising_class:
    def __init__(self, d, steps, t, J, h):
        self.d = d
        self.steps = steps
        self.t = t
        self.J = J
        self.h = h

    def get_trotterized_ising_circuit(self):
        
        """
        Returns a QuantumCircuit implementing a trotterized Ising evolution for d qubits.

        H = - J * sum(Z_i Z_{i+1}) - h * sum(X_i)
        U = exp(-i H t) 
        """
        t = self.t
        steps = self.steps
        d = self.d
        J = self.J
        h = self.h

        dt = t / steps
        qc = QuantumCircuit(d)

        for _ in range(steps):
            # Apply ZZ interactions (Z_i Z_{i+1})
            for i in range(d - 1):
                qc.cx(i, i + 1)
                qc.rz(-2 * J * dt, i + 1)
                qc.cx(i, i + 1)

            # Apply transverse field X terms (X_i)
            for i in range(d):
                qc.rx(-2 * h * dt, i)

        return qc

    def apply_ising_to_registers(self, qc,start):
        """
        Apply trotterized Ising circuit to registers q1, q2, q3 in a 4d-sized register circuit.
        """
        d = self.d
        ising = self.get_trotterized_ising_circuit()

        # Convert to instruction and append to registers q1, q2, q3
        ising_inst = ising.to_instruction()
        for reg in [1, 2, 3]:
            qc.append(ising_inst, [(reg-1) * d + i + start for i in range(d)])

        return qc

    def get_trotterized_ising_statevector(self):
        """
        Returns the statevector from the trotterized Ising evolution of d qubits.
        """
        qc = self.get_trotterized_ising_circuit()
        qc.save_statevector()

        simulator = AerSimulator()
        result = simulator.run(transpile(qc, simulator)).result()
        return result.get_statevector()

def get_QPA_circuit(d, N, ising_circuit,single_control=False,reduced_if=False):
    #FUNCTION TO GET QPA CIRCUIT
    if single_control:
       ncontrols=1
       get_control = lambda x: 0
    else:
       ncontrols=d
       get_control = lambda x: x
    cr_q0 = ClassicalRegister(ncontrols,name='control')
    qr_all = QuantumRegister(3*d+ncontrols)

    # Initialize quantum circuit with classical registers
    qcSWAP = QuantumCircuit(qr_all, cr_q0)  # Extra qubit and classical bit for parity check
    
    qc = ising_circuit.apply_ising_to_registers(qcSWAP,start=ncontrols) #Apply trotterized Ising circuit, 1)
    
    def recursive(N,qc):
      for k in range(ncontrols):
        qc.reset(k)
      qc.h(0)#q0_firstqbit = |0>+|1>/sqrt2
      for k in range(ncontrols-1):
        qc.cx(0,1+k)#q0 = |0000...> + |1111...>/sqrt2
      # Apply the first CSWAP gate controlled by q0, targeting q1 and q2
      for k in range(d):
        qc.cswap(get_control(k), k+ncontrols, k+d+ncontrols)#|+>_k x SYM12_k + |->_k x AntiSYM12_k /norm

      # Apply the second Hadamard gate to q0
      for k in range(ncontrols):
        qc.h(k) #|0> x SYM12 + |1> x AntiSYM12 /norm
      # Measure qubits 0 to d-1 into classical bits 0 to d-1

      for i in range(ncontrols): #Measure the control registers and find z
          qc.measure(i, cr_q0[i])
          if i==0:
            parity_control = qiskit_classical.expr.lift(cr_q0[i])
          else:
            parity_control = qiskit_classical.expr.bit_xor(parity_control, cr_q0[i])

      with qc.if_test(parity_control) as _else:
        #--------Z=1
        pass
      with _else:
        #---------Z = 0
        # qc.x(d+1) # Good test to make sure it's working
        for k in range(d):
          qc.swap(k+d+ncontrols, k+2*d+ncontrols) #Swap q2 with q3
        if not reduced_if:
          if N!=1:
            qc = recursive(N-1,qc) #Do it again unless it was the final iteration of the SWAPNET
            
      if reduced_if:
         if N!=1:
          qc = recursive(N-1,qc)
      return qc
    
    if N!=0:
      qc = recursive(N,qcSWAP)
    else:
      qc = qcSWAP
    # Gets Measure register q3 and save in the classical register
    # for i in range(d):
    #     qc.measure(3*d+i, cr_q0[i]) 
    return qc

def compute_exact_statevector(k, t, J, h):
    """
    Compute the exact statevector for the Ising Hamiltonian:
    H = -J ∑ Z_i Z_{i+1} - h ∑ X_i

    Args:
        k: number of qubits
        t: total evolution time
        J: interaction strength
        h: transverse field strength

    Returns:
        exact_state: Qiskit Statevector object
    """
    dim = 2**k
    I = np.eye(2)
    X = np.array([[0, 1], [1, 0]])
    Z = np.array([[1, 0], [0, -1]])

    def kron_n(*ops):
        out = ops[0]
        for op in ops[1:]:
            out = np.kron(out, op)
        return out

    # Build Hamiltonian
    H = np.zeros((dim, dim), dtype=complex)

    # Z_i Z_{i+1} terms
    for q in range(k - 1):
        ops = [I] * k
        ops[q] = Z
        ops[q + 1] = Z
        H += -J * kron_n(*ops)

    # X_i terms
    for q in range(k):
        ops = [I] * k
        ops[q] = X
        H += -h * kron_n(*ops)

    # Initial state |000>
    psi0 = np.zeros(dim, dtype=complex)
    psi0[0] = 1.0

    # Time evolution: U = exp(-iHt)
    U = expm(-1j * H * t)
    psi_final = U @ psi0

    # Convert to Qiskit Statevector
    return Statevector(psi_final)

def run_qc_and_return_state(qc):

    # Select Aer Simulator backend
    simulator = AerSimulator()

    def execute_circuit_on_state(qc):
        """ Executes a circuit on the AerSimulator and returns the state result. """
        qc_transpiled = transpile(qc, simulator)
        result = simulator.run(qc_transpiled).result()
        return result.get_statevector(qc_transpiled)

    qc.save_statevector()
    state = execute_circuit_on_state(qc)

    return state

def estimate_qc_and_return_distribution(qc,observables,estimator = AerEstimator()):
    pass_manager = generate_preset_pass_manager(3, AerSimulator())
    isa_circuit = pass_manager.run(qc)
    qc_transpiled = transpile(isa_circuit)

    result = estimator.run([(qc_transpiled,observables,None)]).result()
    exp_val = result[0].data.evs
    return exp_val
    # pub_result = result[0]
    # counts = pub_result.data.control.get_counts()
    # return counts


import argparse
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeBrisbane
from qiskit.visualization import plot_error_map
def main():
  parser = argparse.ArgumentParser(
      description="Run the QPA-ising circuit simulation and evaluate fidelity vs noise strength (λ)."
  )

  parser.add_argument('--k', type=int, default=3, metavar='NQUBITS',
                      help='Number of qubits per register (default: 3)')
  parser.add_argument('--shots', type=int, default=1024, metavar='SHOTS',
                      help='Number of shots per circuit execution (default: 1024)')
  parser.add_argument('--t', type=float, default=1.0,
                      help='Total evolution time for Ising circuit (default: 5.0)')
  parser.add_argument('--J', type=float, default=1.0,
                      help='Interaction strength J (default: 1.0)')
  parser.add_argument('--h', type=float, default=1.0,
                      help='Transverse field h (default: 1.0)')
  parser.add_argument('--steps', type=int, default=5,
                      help='Number of Trotter steps (default: 5)')
  parser.add_argument('--output', type=str, default='data/fidelity_fake_backend.csv', metavar='OUTPUT',
                      help='Path to output CSV file (default: data/fidelity_fake_backend.csv)')
  args = parser.parse_args()
  k = args.k
  shots = args.shots
  t, J, h, steps = args.t, args.J, args.h, args.steps
  print('k',k)
  print('shots',shots)
  print('t',t)
  print('J',J)
  print('h',h)
  print('steps',steps)

  #Get Transpiled Circuit for IBM--------------------------------
  # service = QiskitRuntimeService()
  # backend = FakeSherbrooke()
  service = QiskitRuntimeService()
  backend = service.backend("ibm_sherbrooke")

  # 1. Transpile with layout
  ising = ising_class(k, steps, t, J, h)
  trotterized_state = ising.get_trotterized_ising_statevector()

  def get_projector(single_control= False):
      fidelity_operator = SparsePauliOp.from_operator(trotterized_state.to_operator())
      identity_op = SparsePauliOp(["I" * (k)])
      if single_control:
          control_identity = SparsePauliOp(["I"])
      else:
          control_identity = identity_op
      full_space_fidelity_operator = fidelity_operator.tensor(identity_op).tensor(identity_op).tensor(control_identity)
      # full_space_fidelity_operator = identity_op.tensor(fidelity_operator).tensor(identity_op).tensor(control_identity)
      return full_space_fidelity_operator

  single_control = True
  full_space_fidelity_operator = get_projector(single_control)
  fidelities=[]
  nqpa_list = [0,1,2]
  for nqpa in nqpa_list:
    QPA_fake = get_QPA_circuit(k, nqpa, ising,single_control,True)
    qc_transpiled= transpile(QPA_fake, backend=backend, optimization_level=3)

    layout = qc_transpiled.layout
    observable = full_space_fidelity_operator.apply_layout(layout)
    estimator = EstimatorV2(mode=backend)
    estimator.options.default_shots = shots
    job = estimator.run([(qc_transpiled, observable, None)]).result()
    fidelity = job[0].data.evs
    print(f'Found fidelity for nqpa={nqpa}, fidelity={fidelity}')
    fidelities.append(fidelity)
  
  os.makedirs("data", exist_ok=True)
  df = pd.DataFrame({
    'nqpa_list': list(nqpa_list),
    f'Fidelities': fidelities
    })
  
  df.to_csv(args.output, index=False)
  print(f'[+] Output saved to {args.output}')


if __name__ == '__main__':
    main()