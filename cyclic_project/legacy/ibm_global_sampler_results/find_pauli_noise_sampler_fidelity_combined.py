import numpy as np
import os
import csv
from collections import defaultdict
import collections
import pandas as pd
import matplotlib.pyplot as plt

def main():
    
    k=2
    shots=10000
    lambda_min = 0.00
    lambda_max = 0.60
    lambda_steps = 25
    nrandom = 10000
    gatenoise = 0
    aer = 'false'
    fake= 'true'



    data_folder = 'data'
    task_type='ibm_global_sampler'
    simulation_subfolder = 'simulation_outputs'
    plotting_subfolder = 'plotting_results'
    filesuffix = f'k{k}_shots{shots}_lambda{lambda_min}0-{lambda_max}0_s{lambda_steps}_r{nrandom}_g{gatenoise}_aer{aer}_fake{fake}'

    plotting_folder = f'{data_folder}/{task_type}/{plotting_subfolder}'
    simulation_folder = f'{data_folder}/{task_type}/{simulation_subfolder}'

    os.makedirs(plotting_folder,exist_ok=True)
    os.makedirs(simulation_folder,exist_ok=True)

    results_folder = f'{simulation_folder}/{task_type}_{filesuffix}'
    # base_folder = '/home/caiosiq/OQPA/shared_data/pauli_noise_sampler/simulation_outputs/pauli_noise_sampler_k2_shots10240_eps0.0-0.1_s20'
    #base_folder = f'/home/caiosiq/OQPA/shared_data/pauli_noise_sampler/simulation_outputs/pauli_noise_sampler_k{k}_shots{shots}_eps{eps_min}-{eps_max}_s{eps_steps}_r{nrandom}_g{gatenoise}'
    nqpa_dirs = [d for d in os.listdir(results_folder)]
    
    for nqpa_dir in nqpa_dirs:
        nqpa = nqpa_dir[4]
        # Read the combined CSV file
        combined_csv = os.path.join(results_folder, nqpa_dir, "combined_lambda.csv")
        if not os.path.exists(combined_csv):
            print(f"Warning: No combined CSV found in {nqpa_dir}")
            continue
            
        df = pd.read_csv(combined_csv)
        df = df.sort_values("lambda")
        # Extract lambda and fidelity values
        lambda_values = df['lambda'].values
        fidelities = df[f'QPA_{nqpa}'].values
        print(f'Plotting fidelity values for nqpa={nqpa}')    
        print(fidelities)
        print(lambda_values)
        plt.plot(lambda_values, fidelities, label=f'AerFidelity {nqpa}', linestyle='--')
    plt.title(f'QPA Fidelity vs Pauli Noise Strength\n(k={k}, shots={shots}, nrandom={nrandom}, gatenoise={gatenoise})')
    plt.xlabel('Pauli Noise Strength (λ)')
    plt.ylabel('Fidelity')
    plt.legend(title='QPA Rounds')
    plt.grid(True, alpha=0.3)

    plt.savefig(f'{plotting_folder}/{task_type}_{filesuffix}_fidelity.png', dpi=300, bbox_inches='tight')
if __name__ == """__main__""":
    main()
