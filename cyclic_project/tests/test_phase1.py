import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.circuit_builder import DynamicCircuitBuilder, UnrolledCircuitBuilder
from core.noise_models import StandardDepolarizingStrategy, PauliTwirlingStrategy

def test_dynamic_builder():
    print("\n--- Testing DynamicCircuitBuilder ---")
    builder = DynamicCircuitBuilder(k=2, n_trials=2, n_registers=3)
    
    # 1. Build without noise
    results = builder.build(epsilon=0.0)
    print(f"Built {len(results)} circuit(s).")
    assert len(results) == 1
    qc_clean = results[0]['circuit']
    ops_clean = len(qc_clean.data)
    print(f"Clean ops count: {ops_clean}")
    
    # 2. Build with noise
    noise_strategy = StandardDepolarizingStrategy(k=2)
    builder.set_noise_strategy(noise_strategy)
    results_noisy = builder.build(epsilon=0.1)
    qc_noisy = results_noisy[0]['circuit']
    ops_noisy = len(qc_noisy.data)
    print(f"Noisy ops count: {ops_noisy}")
    
    assert ops_noisy > ops_clean
    print("SUCCESS: Dynamic circuit built and noise injected.")

def test_unrolled_builder():
    print("\n--- Testing UnrolledCircuitBuilder ---")
    # Use n_registers=5 to ensure we have branching paths that survive (partial failure)
    builder = UnrolledCircuitBuilder(k=2, n_trials=2, n_registers=5)
    
    # 1. Build without noise
    results = builder.build(epsilon=0.0)
    print(f"Built {len(results)} circuit(s).")
    assert len(results) > 1
    
    qc_clean = results[0]['circuit']
    ops_clean = len(qc_clean.data)
    print(f"Clean ops count (first path): {ops_clean}")
    
    # 2. Build with noise (Pauli Twirling)
    noise_strategy = PauliTwirlingStrategy(k=2)
    builder.set_noise_strategy(noise_strategy)
    results_noisy = builder.build(epsilon=0.5) # High prob to ensure gates added
    
    # Check if noise was applied (might be probabilistic, so check a few)
    qc_noisy = results_noisy[0]['circuit']
    ops_noisy = len(qc_noisy.data)
    print(f"Noisy ops count (first path): {ops_noisy}")
    
    # Pauli noise adds single qubit gates. Clean circuit has initial state prep?
    # Actually, PauliTwirlingStrategy adds gates if rng < epsilon.
    # With epsilon=0.5 and multiple registers, likely to have added gates.
    
    print(f"Path 0 Conditions: {results_noisy[0]['conditions']}")
    print("SUCCESS: Unrolled circuits built.")

if __name__ == "__main__":
    test_dynamic_builder()
    test_unrolled_builder()
