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
    def extract_counts_from_pub_result(pub_result) -> List[Dict[str, int]]:
        """
        Extracts measurement counts from a single PUB result (which may contain multiple parameter sets).
        Returns a list of dictionaries, one per parameter set.
        """
        data = pub_result.data
        
        # Check for anc_meas and readout (Standard Unrolled QPA structure)
        has_anc = hasattr(data, 'anc_meas')
        has_read = hasattr(data, 'readout')
        
        if has_anc and has_read:
            # We need to merge them to preserve correlation
            anc_bits = data.anc_meas.get_bitstrings()
            read_bits = data.readout.get_bitstrings()
            
            # Case 1: Single binding (or aggregated) -> flat list of strings
            # NOTE: If we get a single list of strings, it means there was only one PUB or binding, OR
            # get_bitstrings() already flattened it (unlikely for PrimitiveResult).
            # But let's check the type of the first element.
            if isinstance(anc_bits, list) and len(anc_bits) > 0 and isinstance(anc_bits[0], str):
                 merged = [a + r for a, r in zip(anc_bits, read_bits)]
                 return [dict(Counter(merged))]
                 
            # Case 1b: Empty list
            if isinstance(anc_bits, list) and len(anc_bits) == 0:
                 return [{}]

            # Case 2: Multiple bindings -> list of lists
            # The first element is a LIST of strings.
            if isinstance(anc_bits, list) and len(anc_bits) > 0 and isinstance(anc_bits[0], list):
                result_list = []
                for a_sub, r_sub in zip(anc_bits, read_bits):
                    merged = [a + r for a, r in zip(a_sub, r_sub)]
                    result_list.append(dict(Counter(merged)))
                return result_list
                
            # Fallback for weird cases (e.g. numpy arrays or other containers)
            # Try to iterate and see? Or just assume flat.
            # If anc_bits is numpy array, list(anc_bits) works.
            try:
                # If it's a list of lists (but failed instance check above?)
                if len(anc_bits) > 0 and hasattr(anc_bits[0], '__iter__') and not isinstance(anc_bits[0], str):
                    result_list = []
                    for a_sub, r_sub in zip(anc_bits, read_bits):
                        merged = [a + r for a, r in zip(a_sub, r_sub)]
                        result_list.append(dict(Counter(merged)))
                    return result_list
            except:
                pass

            # Fallback: assume it is flat list of strings
            merged = [a + r for a, r in zip(anc_bits, read_bits)]
            return [dict(Counter(merged))]

        # Fallback to existing logic (single register)
        bit_array = None
        if hasattr(data, 'readout'):
            bit_array = data.readout
        elif hasattr(data, 'meas'):
            bit_array = data.meas
        elif hasattr(data, 'c'):
            bit_array = data.c
        else:
            # Try to find any BitArray
            for attr in dir(data):
                if not attr.startswith('_'):
                    val = getattr(data, attr)
                    if hasattr(val, 'get_counts'):
                        bit_array = val
                        break
        
        if bit_array is not None and hasattr(bit_array, 'get_counts'):
            # get_counts() returns a list of dicts if there are multiple parameter sets
            # or a single dict if only one
            counts = bit_array.get_counts()
            if isinstance(counts, dict):
                return [counts]
            return list(counts)
            
        return [{}]

    @staticmethod
    def extract_counts_from_job_result(pub_result, is_dynamic: bool = False) -> List[Dict[str, int]]:
        """
        Extracts measurement counts from a SamplerV2 PrimitiveResult.
        Handles both single (Unrolled/Dynamic) and multiple (Parameterized) binding sets.
        """
        extracted_counts = []
        
        # Handle iterable results (list or PrimitiveResult)
        try:
            iterator = iter(pub_result)
        except TypeError:
            iterator = [pub_result]
            
        for i, pub_res in enumerate(iterator):
            # Delegate to extract_counts_from_pub_result to handle all cases (Standard vs Parameterized)
            # This handles the anc_meas + readout merging and nested lists correctly.
            counts_list = ResultProcessor.extract_counts_from_pub_result(pub_res)
            
            if not counts_list:
                extracted_counts.append({})
            elif len(counts_list) == 1:
                # Standard case: Single dictionary
                extracted_counts.append(counts_list[0])
            else:
                # Parameterized case: List of dictionaries
                # But extract_counts_from_job_result is expected to return a list where each element
                # corresponds to a PUB result.
                # If we append a list here, extracted_counts becomes List[Union[Dict, List[Dict]]]
                # The caller (retrieve_results.py) handles this structure in the parameterized block.
                extracted_counts.append(counts_list)

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
