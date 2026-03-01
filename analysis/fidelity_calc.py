from typing import Dict

def calculate_success_rate(filtered_counts: Dict[str, int], k: int, total_clbits: int) -> int:
    """
    Calculates the number of shots where the readout register (first k bits) is all zeros.
    
    This function assumes the readout register corresponds to the logical |00..0> state 
    for a successful purification. It extracts the relevant bits from the bitstring 
    and checks if they match the target pattern.
    
    Args:
        filtered_counts (Dict[str, int]): Counts that have already passed the path conditions.
        k (int): Number of qubits in the readout register.
        total_clbits (int): Total classical bits (to locate the readout bits).
        
    Returns:
        int: Number of success shots.
    """
    success_count = 0
    target_pattern = "0" * k
    
    for bitstring, count in filtered_counts.items():
        clean_bitstring = bitstring.replace(" ", "")
        
        # Readout register is typically the first k bits (indices 0 to k-1)
        # In Little-Endian string, these are the LAST k characters
        # Index 0 (LSB) -> String[-1]
        # Index k-1 -> String[-k]
        
        # The slice `clean_bitstring[-k:]` contains bits k-1 down to 0 (reversed order).
        # Since we check for all zeros, "00" reversed is still "00".
        readout_part = clean_bitstring[-k:]
        
        if readout_part == target_pattern:
            success_count += count
            
    return success_count
