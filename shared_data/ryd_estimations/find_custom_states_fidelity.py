import numpy as np
import os
import csv
from collections import defaultdict
import collections
import matplotlib.pyplot as plt

def calculate_base_fidelity(datafile, exact_state_file):
    """
    Calculate base fidelity from input states and exact state.
    
    Args:
        datafile: Path to the input states data file
        exact_state_file: Path to the exact state file
        
    Returns:
        tuple: (avg_base_fidelity, times_on_s2)
    """
    data = np.load(datafile, allow_pickle=True)
    probs = data["probs"]
    input_states = data["states"]
    
    exact_state_data = np.load(exact_state_file, allow_pickle=True)
    exact_state = exact_state_data["state"]
    
    avg_base_fidelity = 0
    times_on_s2 = []
    
    for i, prob in enumerate(probs):
        input_state = input_states[i]
        q3_input_state = input_state[2]
        base_fidelity = np.abs(np.vdot(q3_input_state, exact_state))**2
        avg_base_fidelity += prob * base_fidelity
        
        if base_fidelity < 0.5:
            times_on_s2.append(prob)
    
    times_on_s2 = np.array(times_on_s2)
    print('Probability outside s1:', times_on_s2.sum())
    print('Probability on s1:', probs.sum() - times_on_s2.sum())
    print('Average base fidelity:', avg_base_fidelity)
    
    return avg_base_fidelity, times_on_s2

def calculate_qpa_fidelity(base_folder, probs, avg_base_fidelity, outfile):
    """
    Calculate QPA fidelity from base folder data.
    
    Args:
        base_folder: Path to the base folder containing QPA results
        probs: Probabilities of input states
        avg_base_fidelity: Average base fidelity for reference
        
    Returns:
        dict: {nqpa: {eps: avg_fidelity}}
    """
    fidelity_qpa = defaultdict(list)  # {nqpa: [(epsilon, fidelity_avg), ...]}
    
    # Loop over all input states
    for i, prob in enumerate(probs):
        input_path = os.path.join(base_folder, f"index{i}")
        if not os.path.exists(input_path):
            print(f"Warning: index{i} folder missing. Nothing on {input_path}")
            continue

        for nqpa_folder in os.listdir(input_path):
            if not nqpa_folder.startswith("nqpa"):
                continue

            nqpa_val = int(nqpa_folder.replace("nqpa", ""))
            full_nqpa_path = os.path.join(input_path, nqpa_folder)
            cache = set()
            for filename in os.listdir(full_nqpa_path):
                if not filename.endswith(".csv"):
                    continue

                filepath = os.path.join(full_nqpa_path, filename)
                try:
                    with open(filepath, "r") as f:
                        reader = csv.reader(f)
                        header = next(reader)
                        row = next(reader)
                        eps = float(row[0])
                        fid = float(row[1])
                        if eps not in cache:
                            cache.add(eps)
                            fidelity_qpa[nqpa_val].append((eps, fid * prob))  # weighted by prob
                except Exception as e:
                    print(f"Failed reading {filepath}: {e}")

    final_fidelity_qpa = {}  # {nqpa: {eps: avg_fidelity}}
    for nqpa, entries in fidelity_qpa.items():
        eps_groups = collections.defaultdict(list)
        for eps, fid_weighted in entries:
            eps_groups[eps].append(fid_weighted)
        final_fidelity_qpa[nqpa] = {
            eps: sum(fids) for eps, fids in eps_groups.items()
        }
    
    # Plot results
    plt.figure(figsize=(10, 6))
    for nqpa in sorted(final_fidelity_qpa.keys()):
        # print('NQPA:', nqpa)
        # print('Final fidelity qpa:', final_fidelity_qpa[nqpa])
        eps_list = sorted(final_fidelity_qpa[nqpa].keys())
        fidelities = [final_fidelity_qpa[nqpa][eps] for eps in eps_list]
        plt.plot(eps_list, fidelities, label=f"QPA_{nqpa}")

    plt.axhline(y=avg_base_fidelity, linestyle='--', color='gray', label='Base Fidelity')
    plt.xlabel("Epsilon")
    plt.ylabel("Avg Fidelity")
    plt.title("QPA Fidelity vs Noise")
    plt.legend()
    plt.grid(True)
    #Check how many eigenstates we are using
    print("Number of eigenstates used:", len(probs))
    plt.savefig(outfile)
    
    return final_fidelity_qpa

if __name__ == "__main__":
    nshots = 102400
    k = 4
    eps_steps = 41
    eps_min = 0.0
    eps_max = 0.01
    eigenstates = 5
    base_folder = f'shared_data/ryd_estimations/simulation_outputs/ryd_estimation_{eigenstates**3}_eigenstates_k{k}_shots{nshots}_eps{eps_min}-{eps_max}_s{eps_steps}'
    outfile = f'shared_data/ryd_estimations/plotting_results/fidelity_{eigenstates**3}_k{k}_nshots{nshots}_eps{eps_min}-{eps_max}_s{eps_steps}.png'

    datafile = "shared_data/ryd_estimations/all_states_5_eigenstates.npz"
    exact_state_file = "shared_data/ryd_estimations/exact_state.npz"
    
    # Load data
    data = np.load(datafile, allow_pickle=True)
    probs = data["probs"]
    
    # Calculate base fidelity
    avg_base_fidelity, times_on_s2 = calculate_base_fidelity(datafile, exact_state_file)
    
    # Calculate QPA fidelity
    final_fidelity_qpa = calculate_qpa_fidelity(base_folder, probs, avg_base_fidelity, outfile)
