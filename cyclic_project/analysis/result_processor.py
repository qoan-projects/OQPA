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
        
        # SamplerV2 results are iterable (list of PubResult)
        # But sometimes it might be a single object if not iterable?
        # Usually it's a PrimitiveResult which is iterable.
        
        # Handle case where pub_result is a list (from some backends or older versions)
        # or a PrimitiveResult object.
        try:
            iterator = iter(pub_result)
        except TypeError:
            iterator = [pub_result]
            
        for i, pub_res in enumerate(iterator):
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
                # Check if dynamic usually has other registers?
                # DynamicCircuitBuilder has: res_t0, res_t1... (cr_pool), res_rec, readout
                # But typically we only care about 'readout' for final fidelity?
                # Or do we need to check if intermediate measurements were successful?
                # In DynamicCircuitBuilder, if failure occurs, we don't reach final measure?
                # Or we do?
                
                # If we use get_counts(), it returns a dict of space-separated bitstrings for all registers
                # if they are not named 'readout' specifically?
                # No, data.readout.get_counts() only gets 'readout' register.
                
                # If we want ALL registers (to check conditions), we might need more.
                # But process_dynamic_result assumes we just check readout.
                
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
        # New Logic: Group by condition (path type)
        # We aggregate s_i and N_i for all circuits that share the same condition set (path).
        # Fidelity = Sum_over_paths ( Total_Success_Path / Total_Shots_Path )
        
        # Key: tuple(sorted(conditions.items())) -> Value: {'success': 0, 'total': 0}
        path_stats = {}
        
        for i, counts in enumerate(results):
            meta = circuits_metadata[i]
            # Convert conditions dict to hashable tuple
            conditions = meta.get('conditions', {})
            cond_key = tuple(sorted((int(k), v) for k, v in conditions.items()))
            
            total_clbits = total_clbits_list[i]
            
            # Filter
            filtered = filter_counts(counts, conditions, total_clbits)
            
            # Successes in this path (matching conditions AND readout=0)
            s_i = calculate_success_rate(filtered, self.k, total_clbits)
            
            # Total shots run for THIS circuit
            N_i = get_total_shots(counts) 
            
            if N_i > 0:
                if cond_key not in path_stats:
                    path_stats[cond_key] = {'success': 0, 'total': 0}
                path_stats[cond_key]['success'] += s_i
                path_stats[cond_key]['total'] += N_i
        
        batch_avg_fidelity = 0.0
        for key, stats in path_stats.items():
            if stats['total'] > 0:
                # This is the probability of this path succeeding (averaged over instances in this batch)
                path_prob = stats['success'] / stats['total']
                batch_avg_fidelity += path_prob
                
        return batch_avg_fidelity

    def aggregate_batch_stats(self, 
                            results: List[Dict[str, int]], 
                            circuits_metadata: List[Dict[str, Any]], 
                            total_clbits_list: List[int]) -> Dict[tuple, Dict[str, int]]:
        """
        Aggregates success and total counts per path type for a single batch.
        
        Args:
            results: List of count dictionaries.
            circuits_metadata: List of metadata dictionaries.
            total_clbits_list: List of total classical bits.
            
        Returns:
            Dict[tuple, Dict[str, int]]: A dictionary mapping path condition keys to {'success': int, 'total': int}.
        """
        path_stats = {}
        
        for i, counts in enumerate(results):
            meta = circuits_metadata[i]
            conditions = meta.get('conditions', {})
            cond_key = tuple(sorted((int(k), v) for k, v in conditions.items()))
            
            total_clbits = total_clbits_list[i]
            filtered = filter_counts(counts, conditions, total_clbits)
            s_i = calculate_success_rate(filtered, self.k, total_clbits)
            N_i = get_total_shots(counts)
            
            if N_i > 0:
                if cond_key not in path_stats:
                    path_stats[cond_key] = {'success': 0, 'total': 0}
                path_stats[cond_key]['success'] += s_i
                path_stats[cond_key]['total'] += N_i
                
        return path_stats

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
