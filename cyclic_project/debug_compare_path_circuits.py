
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qiskit import QuantumCircuit
from core.strategies.unrolled import UnrolledStrategy
from core.hybrid_topology import UnrolledHybridStrategy
from core.noise_models import NoiseStrategy

def normalize_circuit_ops(qc):
    """
    Extracts a simplified list of operations for comparison.
    Returns list of (name, qubit_indices, clbit_indices)
    """
    ops = []
    for instruction in qc.data:
        op = instruction.operation
        qubits = [qc.find_bit(q).index for q in instruction.qubits]
        clbits = [qc.find_bit(c).index for c in instruction.clbits]
        
        # Filter out barriers for logical comparison
        if op.name == 'barrier':
            continue
            
        ops.append((op.name, qubits, clbits))
    return ops

def find_circuit_by_path(circuits_data, target_outcomes, key_offset=0):
    """
    Finds a circuit that matches the target outcomes.
    target_outcomes: list of values [0, 1, 0...] for the conditions sorted by key.
    key_offset: Expected start index of condition keys (0 for New, k for Old).
    """
    for item in circuits_data:
        conds = item['conditions']
        if not conds:
            if not target_outcomes: return item['circuit']
            continue
            
        # Sort keys
        sorted_keys = sorted(conds.keys())
        
        # Check if keys match offset
        # This is a weak check, but let's just check values
        values = [conds[k] for k in sorted_keys]
        
        if values == target_outcomes:
            return item['circuit']
    return None

def main():
    N = 5
    k = 2
    T = 3
    
    print(f"Comparing Unrolled Strategies for N={N}, k={k}, T={T}")
    
    # 1. Instantiate Strategies
    # Old: UnrolledHybridStrategy(k, n_trials, n_registers)
    old_strat = UnrolledHybridStrategy(k, T, N)
    
    # New: UnrolledStrategy(k, n_trials, n_registers) - SAME SIGNATURE as Base
    new_strat = UnrolledStrategy(k, T, N)
    
    # 2. Generate Circuits (No Noise)
    print("Generating circuits (epsilon=0)...")
    old_circuits = old_strat.generate_all_paths(epsilon=0.0)
    new_circuits = new_strat.build(epsilon=0.0)
    
    print(f"Old generated {len(old_circuits)} circuits.")
    print("Old Paths:")
    for c in old_circuits:
        # Sort keys and get values
        keys = sorted(c['conditions'].keys())
        vals = [c['conditions'][k] for k in keys]
        print(f"  {vals}")

    print(f"New generated {len(new_circuits)} circuits.")
    print("New Paths:")
    for c in new_circuits:
        keys = sorted(c['conditions'].keys())
        vals = [c['conditions'][k] for k in keys]
        print(f"  {vals}")
    
    # 3. Define Target Path: First pair fails, Second pair succeeds (Outcome 1, 0)
    # This path had 0 success in the logs for the new strategy.
    # We need to trace it deeper.
    # Initial pairs: (0,1), (2,3).
    # Outcome (1, 0) -> Pair (0,1) fails, (2,3) succeeds.
    # Next layer: Survivors + Reserve.
    # Survivor from (2,3) is indices [2,3]. Reserve is [4].
    # Active: [2, 3, 4].
    # New Pairs: (2,3). Reserve: 4.
    # Next outcome: Say 0 (Success).
    # Total outcomes: [1, 0, 0]
    
    # Target Path: Fail (1), Success (0), Success (0), Success (0) -> [1, 0, 0, 0]
    # This corresponds to user log ((0, 1), (1, 0), (2, 0), (3, 0)) -> 0 success
    target_path = [1, 0, 0, 0] 
    print(f"\nAnalyzing Target Path: {target_path} (Fail, Success, Success, Success)")
    
    # Note: Old strategy keys start at k=2. New strategy keys start at 0.
    qc_old = find_circuit_by_path(old_circuits, target_path, key_offset=2)
    qc_new = find_circuit_by_path(new_circuits, target_path, key_offset=0)
    
    if not qc_old:
        print("ERROR: Could not find path in Old strategy")
        return
    if not qc_new:
        print("ERROR: Could not find path in New strategy")
        return
        
    print("Found circuits for both.")
    
    ops_old = normalize_circuit_ops(qc_old)
    ops_new = normalize_circuit_ops(qc_new)
    
    print(f"Old Ops Count: {len(ops_old)}")
    print(f"New Ops Count: {len(ops_new)}")
    
    # 4. Compare Instructions
    import difflib
    old_str = [str(op) for op in ops_old]
    new_str = [str(op) for op in ops_new]
    
    diff = list(difflib.unified_diff(old_str, new_str, fromfile='Old', tofile='New', lineterm=''))
    
    if not diff:
        print("SUCCESS: Circuits are structurally identical!")
    else:
        print("FAIL: Circuits differ!")
        print("Differences (first 50 lines):")
        for line in diff[:50]:
            print(line)

    # 5. Check Registers
    print("\nRegister Check:")
    print("Old Qubits:", len(qc_old.qubits))
    print("New Qubits:", len(qc_new.qubits))
    print("Old Clbits:", len(qc_old.clbits))
    print("New Clbits:", len(qc_new.clbits))

if __name__ == "__main__":
    main()
