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
    
    print(f"Generating unrolled circuits for N={N}, k={k}, n_trials={n_trials}...")
    
    # 1. Create Strategy
    # Note: create_strategy(method, k, n_trials, n_registers)
    strategy = CircuitFactory.create_strategy('unrolled', k, n_trials, N)
    
    # 2. Build Circuits (epsilon=0.01 to include some noise ops for realism, or 0.0)
    circuits_data = strategy.build(epsilon=0.01) 
    
    print(f"Generated {len(circuits_data)} circuits/branches.")
    
    # 3. Transpile
    print("Getting backend 'ibm_boston' (or fake equivalent)...")
    try:
        # Try to use the handler's logic
        handler = FakeBackendHandler("ibm_boston")
        backend = handler.get_backend()
    except Exception as e:
        print(f"Could not get ibm_boston: {e}")
        print("Falling back to fake_brisbane")
        handler = FakeBackendHandler("fake_brisbane")
        backend = handler.get_backend()

    print(f"Transpiling for backend: {backend.name}")
    
    ts = TranspilerService(backend, optimization_level=3)
    
    raw_circuits = [d['circuit'] for d in circuits_data]
    transpiled_circuits = ts.transpile(raw_circuits)
    
    if not isinstance(transpiled_circuits, list):
        transpiled_circuits = [transpiled_circuits]
        
    # 4. Find Longest Branch
    # We judge by depth
    max_depth = -1
    longest_idx = -1
    
    for i, qc in enumerate(transpiled_circuits):
        depth = qc.depth()
        if depth > max_depth:
            max_depth = depth
            longest_idx = i
            
    longest_qc = transpiled_circuits[longest_idx]
    longest_meta = circuits_data[longest_idx]['metadata']
    conditions = circuits_data[longest_idx]['conditions']
    
    print(f"Longest branch found: Index {longest_idx}")
    print(f"Metadata: {longest_meta}")
    print(f"Conditions: {conditions}")
    print(f"Depth: {max_depth}")
    
    # 5. Print Gate Counts
    ops = longest_qc.count_ops()
    print("\nGate Counts:")
    n_1q = 0
    n_2q = 0
    
    # 2q gates on IBM: ecr, cz, cx, rzx, etc.
    two_q_gates = ['ecr', 'cx', 'cz', 'rzx', 'swap', 'cswap']
    
    for gate, count in ops.items():
        print(f"  {gate}: {count}")
        if gate in two_q_gates:
            n_2q += count
        elif gate not in ['measure', 'barrier', 'reset', 'delay']:
            n_1q += count
            
    print(f"\nTotal 1-qubit gates: {n_1q}")
    print(f"Total 2-qubit gates: {n_2q}")
    
    # 6. Plot
    output_filename = './longest_branch_unrolled_circuit_boston.png'
    print(f"\nPlotting circuit to '{output_filename}'...")
    try:
        longest_qc.draw(output='mpl', filename=output_filename)
        print("Plot saved.")
    except Exception as e:
        print(f"Failed to plot with mpl: {e}")
        print("Trying text draw...")
        print(longest_qc.draw(output='text'))

if __name__ == "__main__":
    main()
