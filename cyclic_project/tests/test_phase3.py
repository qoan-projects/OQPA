import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analysis.result_processor import ResultProcessor

def test_result_processing():
    print("\n--- Testing Result Processor ---")
    
    k = 2
    processor = ResultProcessor(k=k)
    
    # Mock Data
    # Circuit 1: Expect Ancilla (bit 2) = 0
    # Bitstring: Anc R1 R0
    counts1 = {
        '000': 50, # Anc=0, R=00 -> Success, Match Condition
        '010': 10, # Anc=0, R=10 -> Fail, Match Condition
        '100': 40  # Anc=1, R=00 -> Success, Mismatch Condition (Should be filtered)
    }
    meta1 = {'conditions': {2: 0}} # Ancilla at index 2 must be 0
    total_clbits1 = 3
    
    # Circuit 2: Expect Ancilla (bit 2) = 1
    counts2 = {
        '100': 30, # Anc=1, R=00 -> Success, Match Condition
        '000': 20  # Anc=0, R=00 -> Success, Mismatch Condition (Should be filtered)
    }
    meta2 = {'conditions': {2: 1}} # Ancilla at index 2 must be 1
    total_clbits2 = 3
    
    results = [counts1, counts2]
    metadata = [meta1, meta2]
    clbits = [total_clbits1, total_clbits2]
    
    fidelity = processor.process_unrolled_results(results, metadata, clbits)
    
    print(f"Calculated Fidelity: {fidelity:.4f}")
    
    # Expected:
    # Path 1: Valid=60, Success=50
    # Path 2: Valid=30, Success=30
    # Total: Valid=90, Success=80
    # Fid = 80/90 = 0.8888...
    
    expected = 80/90
    assert abs(fidelity - expected) < 1e-6
    print("SUCCESS: Fidelity calculation is correct.")

if __name__ == "__main__":
    test_result_processing()
