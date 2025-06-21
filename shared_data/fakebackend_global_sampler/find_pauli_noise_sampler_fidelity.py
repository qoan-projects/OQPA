import numpy as np
import os
import csv
from collections import defaultdict
import collections
import pandas as pd
import matplotlib.pyplot as plt
k=2
shots=10240000
eps_min = 0.0
eps_max = 0.1
eps_steps = 41
nrandom = 1000
gatenoise = 0.05
# base_folder = '/home/caiosiq/OQPA/shared_data/pauli_noise_sampler/simulation_outputs/pauli_noise_sampler_k2_shots10240_eps0.0-0.1_s20'
base_folder = f'/home/caiosiq/OQPA/shared_data/pauli_noise_sampler/simulation_outputs/pauli_noise_sampler_k{k}_shots{shots}_eps{eps_min}-{eps_max}_s{eps_steps}_r{nrandom}_g{gatenoise}'
nqpa_dirs = [d for d in os.listdir(base_folder)]
for nqpa_dir in nqpa_dirs:
        print(nqpa_dir)
        nqpa = int(nqpa_dir[-1])  # Extract nqpa from directory name
        eps_values = []
        fidelities = []
        
        # Get all CSV files in this nqpa directory
        csv_files = [f for f in os.listdir(os.path.join(base_folder, nqpa_dir)) if f.endswith('.csv')]
        
        # Sort CSV files by epsilon value (extracted from filename)
        csv_files.sort(key=lambda x: int(x.split('_')[2].replace('eps', '').replace('.csv', '')))
        
        for csv_file in csv_files:
            df = pd.read_csv(os.path.join(base_folder, nqpa_dir, csv_file))
            eps = df.iloc[0]['epsilon']  # Get epsilon value from CSV
            fidelity = df.iloc[0][f'QPA_{nqpa}']  # Get fidelity value
            eps_values.append(eps)
            fidelities.append(fidelity)
        
        plt.plot(eps_values, fidelities, label=f'AerFidelity {nqpa}', linestyle='--')
plt.title(f'QPA Fidelity vs Pauli Noise Strength\n(k={k}, shots={shots}, nrandom={nrandom}, gatenoise={gatenoise})')
plt.xlabel('Pauli Noise Strength (ε)')
plt.ylabel('Fidelity')
plt.legend(title='QPA Rounds')
plt.grid(True, alpha=0.3)
plt.savefig(f'/home/caiosiq/OQPA/shared_data/pauli_noise_sampler/plotting_results/k{k}_shots{shots}_eps{eps_min}-{eps_max}_s{eps_steps}_r{nrandom}_g{gatenoise}_fidelity.png', dpi=300, bbox_inches='tight')