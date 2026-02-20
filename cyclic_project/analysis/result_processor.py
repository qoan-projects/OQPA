from typing import List, Dict, Any, Optional
from collections import Counter
from analysis.fidelity_calc import calculate_success_rate

class ResultProcessor:
    """
    Aggregates and processes raw measurement counts to compute QPA fidelity.
    """
    def __init__(self, k: int):
        self.k = k

    @staticmethod
    def extract_counts_from_job_result(pub_result, is_dynamic: bool = False) -> List[Dict[str, int]]:
        """
        Extracts measurement counts from a SamplerV2 PrimitiveResult.
        """
        extracted_counts = []
        
        # Handle iterable results (list or PrimitiveResult)
        try:
            iterator = iter(pub_result)
        except TypeError:
            iterator = [pub_result]
            
        for i, pub_res in enumerate(iterator):
            data = pub_res.data
            
            # Check for specific register names
            has_anc = hasattr(data, 'anc_meas')
            has_read = hasattr(data, 'readout')
            
            if not is_dynamic and has_anc and has_read:
                # Unrolled: Merge 'anc_meas' (MSB) and 'readout' (LSB)
                if data.anc_meas.num_bits == 0:
                    read_strs = data.readout.get_bitstrings()
                    extracted_counts.append(dict(Counter(read_strs)))
                else:
                    anc_strs = data.anc_meas.get_bitstrings()
                    read_strs = data.readout.get_bitstrings()
                    merged = [a + r for a, r in zip(anc_strs, read_strs)]
                    extracted_counts.append(dict(Counter(merged)))
                
            elif hasattr(data, 'meas'): 
                # Fallback: if measure_all() was used
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
                    extracted_counts.append({})

        return extracted_counts

    def process_unrolled_results(self, 
                                 results: List[Dict[str, int]], 
                                 circuits_metadata: List[Dict[str, Any]],
                                 total_clbits_list: List[int]) -> float:
        """
        Computes the global fidelity from a list of unrolled circuit results.
        """
        path_stats = self.aggregate_batch_stats(results, circuits_metadata, total_clbits_list)
        
        batch_avg_fidelity = 0.0
        for key, stats in path_stats.items():
            if stats['total'] > 0:
                path_prob = stats['success'] / stats['total']
                batch_avg_fidelity += path_prob
                
        return batch_avg_fidelity

    def aggregate_batch_stats(self, 
                            results: List[Dict[str, int]], 
                            circuits_metadata: List[Dict[str, Any]], 
                            total_clbits_list: List[int]) -> Dict[tuple, Dict[str, int]]:
        """
        Aggregates success and total counts per path type for a single batch.
        """
        path_stats = {}
        
        for i, counts in enumerate(results):
            meta = circuits_metadata[i]
            conditions = meta.get('conditions', {})
            cond_key = tuple(sorted((int(k), v) for k, v in conditions.items()))
            
            total_clbits = total_clbits_list[i]
            
            # Filter
            filtered = self._filter_counts(counts, conditions, total_clbits)
            s_i = calculate_success_rate(filtered, self.k, total_clbits)
            N_i = sum(counts.values())
            
            if N_i > 0:
                if cond_key not in path_stats:
                    path_stats[cond_key] = {'success': 0, 'total': 0}
                path_stats[cond_key]['success'] += s_i
                path_stats[cond_key]['total'] += N_i
                
        return path_stats

    def process_dynamic_result(self, counts: Dict[str, int], total_clbits: int) -> float:
        """
        Computes fidelity for a single dynamic circuit result.
        """
        total_shots = sum(counts.values())
        if total_shots == 0:
            return 0.0
            
        success_shots = calculate_success_rate(counts, self.k, total_clbits)
        return success_shots / total_shots

    def _filter_counts(self, counts: Dict[str, int], conditions: Dict[int, int], total_clbits: int) -> Dict[str, int]:
        """
        Filters measurement counts based on post-selection conditions.
        """
        if not conditions:
            return counts.copy()
            
        filtered_counts = {}
        for bitstring, count in counts.items():
            clean_bitstring = bitstring.replace(" ", "")
            match = True
            for clbit_idx, expected_val in conditions.items():
                # Qiskit bitstring is Little-Endian
                str_idx = len(clean_bitstring) - 1 - clbit_idx
                if str_idx < 0 or str_idx >= len(clean_bitstring):
                    match = False
                    break
                if int(clean_bitstring[str_idx]) != expected_val:
                    match = False
                    break
            
            if match:
                filtered_counts[bitstring] = count
                
        return filtered_counts
