from typing import List, Dict, Any
from analysis.post_selection import filter_counts, get_total_shots
from analysis.fidelity_calc import calculate_success_rate
from collections import Counter

class ResultProcessor:
    """
    Aggregates and processes raw measurement counts to compute QPA fidelity.
    """
    def __init__(self, k: int):
        """
        Args:
            k (int): Number of qubits per register (target size).
        """
        self.k = k

    @staticmethod
    def extract_counts_from_job_result(pub_result, is_dynamic: bool = False) -> List[Dict[str, int]]:
        """
        Extracts measurement counts from a SamplerV2 PrimitiveResult.
        
        Args:
            pub_result: The result object from SamplerV2.
            is_dynamic (bool): Whether the circuits are dynamic (readout only) or unrolled (readout + ancilla).
            
        Returns:
            List[Dict[str, int]]: A list of dictionaries containing measurement counts for each circuit.
        """
        extracted_counts = []
        
        for i, pub_res in enumerate(pub_result):
            data = pub_res.data
            
            has_anc = hasattr(data, 'anc_meas')
            has_read = hasattr(data, 'readout')
            
            if not is_dynamic and has_anc and has_read:
                # Unrolled: Merge 'anc_meas' (MSB) and 'readout' (LSB)
                
                # Handle case where anc_meas is empty (e.g. n_trials=0)
                if data.anc_meas.num_bits == 0:
                    # Only readout matters
                    read_strs = data.readout.get_bitstrings()
                    extracted_counts.append(dict(Counter(read_strs)))
                else:
                    anc_strs = data.anc_meas.get_bitstrings()
                    read_strs = data.readout.get_bitstrings()
                    merged = [a + r for a, r in zip(anc_strs, read_strs)]
                    extracted_counts.append(dict(Counter(merged)))
                
            elif hasattr(data, 'meas'): 
                # Fallback: if measure_all() was used or single register
                extracted_counts.append(data.meas.get_counts())
                
            elif has_read:
                # Dynamic or simple readout
                extracted_counts.append(data.readout.get_counts())
                
            else:
                # Fallback: try to find any BitArray
                found = False
                for attr in dir(data):
                    if not attr.startswith('_'):
                        val = getattr(data, attr)
                        if hasattr(val, 'get_counts'):
                            extracted_counts.append(val.get_counts())
                            found = True
                            break
                if not found:
                    print(f"Warning: No valid measurements found for circuit {i}")
                    extracted_counts.append({})

        return extracted_counts

    def process_unrolled_results(self, 
                                 results: List[Dict[str, int]], 
                                 circuits_metadata: List[Dict[str, Any]],
                                 total_clbits_list: List[int]) -> float:
        """
        Computes the global fidelity from a list of unrolled circuit results.
        
        The method aggregates data from multiple circuits, where each circuit represents 
        a specific path in the probabilistic decision tree. It filters shots based on 
        ancilla measurements (conditions) and then calculates the success rate of the 
        final purified state.
        
        Args:
            results (List[Dict[str, int]]): List of count dictionaries (one per circuit path).
            circuits_metadata (List[Dict[str, Any]]): List of metadata dicts containing 'conditions'.
            total_clbits_list (List[int]): List of total clbits for each circuit (needed for parsing).
            
        Returns:
            float: Global Fidelity (0.0 to 1.0).
        """
        global_fidelity = 0.0
        
        for i, counts in enumerate(results):
            meta = circuits_metadata[i]
            conditions = meta.get('conditions', {})
            total_clbits = total_clbits_list[i]
            
            # Filter
            filtered = filter_counts(counts, conditions, total_clbits)
            
            # Successes in this path
            s_i = calculate_success_rate(filtered, self.k, total_clbits)
            
            # Total shots run for THIS circuit
            # We need the raw total shots from the counts (before filtering)
            N_i = get_total_shots(counts) 
            
            if N_i > 0:
                global_fidelity += (s_i / N_i)
                
        return global_fidelity

    def process_dynamic_result(self, counts: Dict[str, int], total_clbits: int) -> float:
        """
        Computes fidelity for a single dynamic circuit result.
        
        For dynamic circuits, branching logic is internal. We assume that if the circuit 
        completes, the result is in the readout register.
        
        Args:
            counts (Dict[str, int]): Measurement counts from the dynamic circuit.
            total_clbits (int): Total classical bits.

        Returns:
            float: Fidelity (Success Rate).
        """
        # Dynamic circuit has no external conditions to filter? 
        # Or does it? Usually dynamic circuits rely on internal if_test.
        # So we just check the readout register.
        
        total_shots = get_total_shots(counts)
        success_shots = calculate_success_rate(counts, self.k, total_clbits)
        
        if total_shots == 0:
            return 0.0
            
        return success_shots / total_shots
