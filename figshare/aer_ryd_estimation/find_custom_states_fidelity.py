import numpy as np
import os
import csv
from collections import defaultdict
import matplotlib.pyplot as plt

def calculate_base_fidelity(datafile, exact_state_file):
    """Calculate base fidelity from input states and exact state."""
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
    """Calculate QPA fidelity from merged_results.csv files and plot results."""
    fidelity_qpa = defaultdict(list)
    counts_qpa = defaultdict(lambda: defaultdict(int))
    probsum_qpa = defaultdict(lambda: defaultdict(float))

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
            merged_path = os.path.join(full_nqpa_path, "merged_results.csv")
            if not os.path.isfile(merged_path):
                print(f"Missing: {merged_path}")
                continue

            try:
                with open(merged_path, "r") as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    for row in reader:
                        eps = float(row[0])
                        fid = float(row[1])
                        fidelity_qpa[nqpa_val].append((eps, fid * prob))
                        counts_qpa[nqpa_val][eps] += 1
                        probsum_qpa[nqpa_val][eps] += prob
            except Exception as e:
                print(f"Failed reading {merged_path}: {e}")

    final_fidelity_qpa = {}
    for nqpa, entries in fidelity_qpa.items():
        eps_groups = defaultdict(list)
        for eps, fid_weighted in entries:
            eps_groups[eps].append(fid_weighted)
        final_fidelity_qpa[nqpa] = {eps: sum(fids) for eps, fids in eps_groups.items()}

    # Plot results
    plt.figure(figsize=(10, 6))
    for nqpa in sorted(final_fidelity_qpa.keys()):
        eps_list = sorted(final_fidelity_qpa[nqpa].keys())
        fidelities = [final_fidelity_qpa[nqpa][eps] for eps in eps_list]
        print(f"-------- QPA {nqpa} --------")
        print("Epsilons:", eps_list)
        print("Fidelities:", fidelities)
        plt.plot(eps_list, fidelities, label=f"QPA_{nqpa}")

    plt.axhline(avg_base_fidelity, color='gray', linestyle='--', label='Base fidelity')
    plt.xlabel("ε (Depolarizing strength)")
    plt.ylabel("Average Fidelity")
    plt.title("QPA Fidelity vs ε")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outfile)

    return final_fidelity_qpa

if __name__ == "__main__":
    nshots = 102400
    k = 4
    eps_steps = 41
    eps_min = 0.0
    eps_max = 0.01
    eigenstates = 5
    base_folder = f'shared_data/aer_ryd_estimation/simulation_outputs/ryd_estimation_{eigenstates**3}_eigenstates_k{k}_shots{nshots}_eps{eps_min}-{eps_max}_s{eps_steps}'
    outfile = f'shared_data/aer_ryd_estimation/plotting_results/fidelity_{eigenstates**3}_k{k}_nshots{nshots}_eps{eps_min}-{eps_max}_s{eps_steps}.png'

    datafile = "shared_data/aer_ryd_estimation/all_states_5_eigenstates.npz"
    exact_state_file = "shared_data/aer_ryd_estimation/exact_state.npz"
    
    data = np.load(datafile, allow_pickle=True)
    probs = data["probs"]
    
    avg_base_fidelity, times_on_s2 = calculate_base_fidelity(datafile, exact_state_file)
    
    final_fidelity_qpa = calculate_qpa_fidelity(base_folder, probs, avg_base_fidelity, outfile)
