import sys
import os
import matplotlib.pyplot as plt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.circuit_factory import CircuitFactory
from execution.transpiler_service import TranspilerService
from execution.backend_handler import FakeBackendHandler
from qiskit import transpile

def main():
    N = 7
    k = 2
    n_trials = 3
    
    print(f"Generating DYNAMIC circuit for N={N}, k={k}, n_trials={n_trials}...")
    
    # 1. Create Strategy
    # Note: create_strategy(method, k, n_trials, n_registers)
    strategy = CircuitFactory.create_strategy('dynamic', k, n_trials, N)
    
    # 2. Build Circuits (epsilon=0.01 to include some noise ops for realism, or 0.0)
    circuits_data = strategy.build(epsilon=0.01) 
    
    print(f"Generated {len(circuits_data)} circuit(s).")
    
    # 3. Transpile
    print("Getting backend 'ibm_boston' (or fake equivalent)...")
    try:
        # Get REAL backend directly to test transpilation
        from execution.backend_handler import IBMRuntimeHandler
        handler = IBMRuntimeHandler("ibm_boston")
        backend = handler.get_backend()
        
        # Check transpilation capability
        print(f"Checking transpilation for {backend.name}...")
        ts = TranspilerService(backend, optimization_level=3)
        # We don't need to actually submit, just transpile
        transpiled_circuits = ts.transpile([d['circuit'] for d in circuits_data])
        print(f"Transpilation check passed for {backend.name}.")
        
        # If successful, use this backend
        if not isinstance(transpiled_circuits, list):
             transpiled_circuits = [transpiled_circuits]
             
    except Exception as e:
        print(f"Issue with ibm_boston (backend or transpilation): {e}")
        # Stop script if we strictly want to test ibm_boston transpilation
        # But if you want to see the error and stop:
        sys.exit(1)

    if not isinstance(transpiled_circuits, list):
        transpiled_circuits = [transpiled_circuits]
        
    qc = transpiled_circuits[0]
    meta = circuits_data[0]['metadata']
    
    print(f"Transpilation complete.")
    print(f"Metadata: {meta}")
    print(f"Depth: {qc.depth()}")
    
    # 5. Print Gate Counts
    ops = qc.count_ops()
    print("\nGate Counts:")
    n_1q = 0
    n_2q = 0
    
    # 2q gates on IBM: ecr, cz, cx, rzx, etc.
    two_q_gates = ['ecr', 'cx', 'cz', 'rzx', 'swap', 'cswap']
    
    for gate, count in ops.items():
        print(f"  {gate}: {count}")
        if gate in two_q_gates:
            n_2q += count
        elif gate not in ['measure', 'barrier', 'reset', 'delay', 'if_else', 'while_loop', 'for_loop', 'switch_case']:
            n_1q += count
            
    print(f"\nTotal 1-qubit gates: {n_1q}")
    print(f"Total 2-qubit gates: {n_2q}")
    print(f"(Note: Control flow instructions like if_else are not counted as 1q/2q gates here)")
    
    # 6. Plot
    output_filename = './dynamical_circuit_boston.png'
    print(f"\nPlotting circuit to '{output_filename}'...")
    try:
        # For dynamic circuits, plotting might be huge.
        qc.draw(output='mpl', filename=output_filename)
        print("Plot saved.")
    except Exception as e:
        print(f"Failed to plot with mpl: {e}")
        print("Trying text draw...")
        print(qc.draw(output='text'))

if __name__ == "__main__":
    main()
