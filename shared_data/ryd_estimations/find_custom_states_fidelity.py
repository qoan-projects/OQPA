import numpy as np
import os
import csv
from collections import defaultdict
import collections

base_folder = '/home/caiosiq/OQPA/data/ryd_estimation_k4_shots102400_eps0.0-0.01_s41'
datafile = "/home/caiosiq/OQPA/shared_data/ryd_estimations/all_states.npz"
data = np.load(datafile, allow_pickle=True)
probs = data["probs"]
# probs = probs/probs.sum()
input_states = data["states"]
avg_base_fidelity=0
print(input_states.shape)
print(probs.sum())
exact_state_file = "/home/caiosiq/OQPA/shared_data/ryd_estimations/exact_state.npz"
exact_state_data = np.load(exact_state_file, allow_pickle=True)
exact_state = exact_state_data["state"]
times_on_s2=[]


fidelity_qpa={} # Dictionary of fidelities npqa:{eps1:fidelity1,eps2:fidelity2,...}
for i,prob in enumerate(probs):
    input_state = input_states[i]
    q3_input_state = input_state[2]
    base_fidelity = np.abs(np.vdot(q3_input_state, exact_state))**2
    print('For input i, base_fidelity of:',base_fidelity, 'probability of:', prob)
    avg_base_fidelity += prob*base_fidelity
    if base_fidelity<0.5:
        times_on_s2.append(prob)
    
times_on_s2 = np.array(times_on_s2)
print('Probability outside s1:', times_on_s2.sum())
print('Probability on s1:', probs.sum()-times_on_s2.sum())

print(avg_base_fidelity)


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
                    fidelity_qpa[nqpa_val].append((eps, fid * prob))  # weighted by prob
            except Exception as e:
                print(f"Failed reading {filepath}: {e}")


final_fidelity_qpa = {}  # {nqpa: {eps: avg_fidelity}}

for nqpa, entries in fidelity_qpa.items():
    eps_groups = collections.defaultdict(list)
    for eps, fid_weighted in entries:
        eps_groups[eps].append(fid_weighted) #{eps:[fidelity1_weighted,fidelity2_weighted,fidelity3_weighted]}
    final_fidelity_qpa[nqpa] = {
        eps: sum(fids) for eps, fids in eps_groups.items()
    }


import matplotlib.pyplot as plt

for nqpa in sorted(final_fidelity_qpa.keys()):
    eps_list = sorted(final_fidelity_qpa[nqpa].keys())
    fidelities = [final_fidelity_qpa[nqpa][eps] for eps in eps_list]
    plt.plot(eps_list, fidelities, label=f"QPA_{nqpa}")

plt.axhline(y=avg_base_fidelity, linestyle='--', color='gray', label='Base Fidelity')
plt.xlabel("Epsilon")
plt.ylabel("Avg Fidelity")
plt.title("QPA Fidelity vs Noise")
plt.legend()
plt.grid(True)
plt.savefig('/home/caiosiq/OQPA/shared_data/ryd_estimations/fidelity.png')
