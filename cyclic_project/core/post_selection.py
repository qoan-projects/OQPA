# qpa_project/core/post_selection.py

def process_results(counts, conditions):
    """
    counts: Dict {'bitstring': count}
    conditions: Dict {clbit_index: expected_value}
    
    Returns: Filtered counts for the readout register.
    """
    filtered_counts = {}
    
    for bitstr, count in counts.items():
        # bitstr is usually "anc_meas readout" (check Qiskit bit ordering!)
        # Qiskit returns bits right-to-left. 
        # Need to parse carefully based on circuit layout.
        
        # Pseudo-code parsing:
        bits = [int(b) for b in bitstr] # Convert to list of ints
        
        valid = True
        for idx, val in conditions.items():
            # Check if bit at 'idx' matches 'val'
            # Note: You must map 'idx' (from classical register) to position in bitstring
            if bits[idx] != val:
                valid = False
                break
        
        if valid:
            # Extract only readout part
            readout_part = extract_readout(bitstr)
            filtered_counts[readout_part] = filtered_counts.get(readout_part, 0) + count
            
    return filtered_counts