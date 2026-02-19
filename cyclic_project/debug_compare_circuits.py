
import sys
import numpy as np
from qiskit import QuantumCircuit, transpile
from core.strategies.dynamic import DynamicStrategy
from core.circuit_builder import DynamicCircuitBuilder
from core.noise_models import StandardDepolarizingStrategy

def compare_circuits():
    print("--- Comparing DynamicStrategy (New) vs DynamicCircuitBuilder (Old/Ref) ---")
    
    # Parameters
    n = 5
    k = 2
    trials = 3
    epsilon = 0.1 # Some noise to trigger noise ops if any
    
    # 1. Build with New Strategy
    print("\n[1] Building New Strategy Circuit...")
    strategy = DynamicStrategy(n_registers=n, k=k, n_trials=trials)
    # Add noise strategy to be fair comparison
    noise_strat = StandardDepolarizingStrategy(k)
    strategy.set_noise_strategy(noise_strat)
    
    # Build
    # Note: Strategy.build returns a list of dicts
    circuits_data_new = strategy.build(epsilon)
    qc_new = circuits_data_new[0]['circuit']
    
    # 2. Build with Old Builder
    print("\n[2] Building Old Builder Circuit...")
    builder = DynamicCircuitBuilder(n_registers=n, k=k, n_trials=trials)
    builder.set_noise_strategy(noise_strat)
    
    circuits_data_old = builder.build(epsilon)
    qc_old = circuits_data_old[0]['circuit']
    
    # 3. Compare
    print("\n--- Comparison Results ---")
    print(f"New Circuit Depth: {qc_new.depth()}")
    print(f"Old Circuit Depth: {qc_old.depth()}")
    
    print(f"New Circuit Ops: {qc_new.count_ops()}")
    print(f"Old Circuit Ops: {qc_old.count_ops()}")
    
    # Check QASM (ignoring register names if possible, but they should be similar)
    # We might need to normalize register names or just check structure.
    
    # Let's check instructions count
    if qc_new.count_ops() == qc_old.count_ops():
        print("PASS: Operation counts match.")
    else:
        print("FAIL: Operation counts do NOT match.")
        
    # Check if they have the same number of qubits/clbits
    print(f"New Qubits: {qc_new.num_qubits}, Clbits: {qc_new.num_clbits}")
    print(f"Old Qubits: {qc_old.num_qubits}, Clbits: {qc_old.num_clbits}")
    
    # Deep comparison of instructions
    # This is tricky due to potential register naming differences or order.
    # But let's look at the first few instructions.
    
    print("\n[First 10 Instructions - New]")
    for instr in qc_new.data[:10]:
        print(f"  {instr.operation.name} {instr.qubits} {instr.clbits}")
        
    print("\n[First 10 Instructions - Old]")
    for instr in qc_old.data[:10]:
        print(f"  {instr.operation.name} {instr.qubits} {instr.clbits}")
        
    # Check QASM equality?
    # qasm_new = qc_new.qasm()
    # qasm_old = qc_old.qasm()
    # if qasm_new == qasm_old:
    #     print("PASS: QASM strings are identical.")
    # else:
    #     print("FAIL: QASM strings differ.")

if __name__ == "__main__":
    compare_circuits()
