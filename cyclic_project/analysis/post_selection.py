from typing import Dict, Any

def filter_counts(counts: Dict[str, int], conditions: Dict[int, int], total_clbits: int) -> Dict[str, int]:
    """
    Filters measurement counts based on post-selection conditions.
    
    This function checks each bitstring in the counts dictionary against a set of 
    expected values for specific classical bits (ancilla measurements). Only 
    shots that match the conditions are retained.
    
    Args:
        counts (Dict[str, int]): Dictionary of {bitstring: count}.
        conditions (Dict[int, int]): Dictionary of {clbit_index: expected_value}.
        total_clbits (int): Total number of classical bits in the circuit (to map indices correctly).
        
    Returns:
        Dict[str, int]: Filtered dictionary of counts.
    """
    if not conditions:
        return counts.copy()
        
    filtered_counts = {}
    
    for bitstring, count in counts.items():
        # Remove spaces if present (Qiskit sometimes adds them between registers)
        clean_bitstring = bitstring.replace(" ", "")
        
        # Verify length
        if len(clean_bitstring) != total_clbits:
            # If length mismatch, it might be due to leading zeros being omitted or different format
            # But usually SamplerV2 returns full width. 
            pass

        match = True
        for clbit_idx, expected_val in conditions.items():
            # Qiskit bitstring is Little-Endian: index 0 is at -1 (last char)
            # index i is at len - 1 - i
            str_idx = len(clean_bitstring) - 1 - clbit_idx
            
            if str_idx < 0 or str_idx >= len(clean_bitstring):
                # Should not happen if total_clbits is correct
                match = False
                break
                
            actual_val = int(clean_bitstring[str_idx])
            if actual_val != expected_val:
                match = False
                break
        
        if match:
            filtered_counts[bitstring] = count
            
    return filtered_counts

def get_total_shots(counts: Dict[str, int]) -> int:
    """Returns the sum of all counts in the dictionary."""
    return sum(counts.values())
