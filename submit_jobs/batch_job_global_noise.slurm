#!/bin/bash 
#SBATCH --job-name=qpa_simulation
#SBATCH --output=../data/logs/%x_%j.out
#SBATCH --error=../data/logs/%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=256G
#SBATCH --cpus-per-task=40
#SBATCH --time=12:00:00
#SBATCH --partition=mit_normal

# --- Job Name Configuration ---
# Uncomment the line corresponding to the example you are running to get specific log names.
# Default: qpa_simulation

# Example 1: AER Dynamic
# #SBATCH --job-name=aer_dynamic_new

# Example 2: AER Unrolled
# #SBATCH --job-name=aer_unrolled_new

# Example 3: Fake Backend
# #SBATCH --job-name=fake_run_new

# Example 4: IBM Post-Only
# #SBATCH --job-name=ibm_submit_new

# Example 5: Retrieve IBM
# #SBATCH --job-name=ibm_retrieve_new

# Example 6: Retrieve AER
# #SBATCH --job-name=aer_retrieve_new

# Example 7: Retrieve Fake
# #SBATCH --job-name=fake_retrieve_new

# Example 8: Retrieve AER
# #SBATCH --job-name=aer_retrieve_dynamical_new

# Example 9: IBM Parametrized Post-Only
# #SBATCH --job-name=ibm_parametrized_submit_new

# Example 10: IBM Parametrized Retrieve-Only
#SBATCH --job-name=ibm_parametrized_retrieve_new

# Example 11: Fake Parametrized Post-Only
# #SBATCH --job-name=fake_parametrized_submit_new

# Example 12: AER Parametrized Post-Only
# #SBATCH --job-name=aer_parametrized_submit_new

# Example 13: AER Parametrized Retrieve-Only
# #SBATCH --job-name=aer_parametrized_retrieve_new

# Example 14: Fake Parametrized No Reset
# #SBATCH --job-name=fake_parametrized_no_reset

# Example 15: IBM Parametrized No Reset Post-Only
# #SBATCH --job-name=ibm_parametrized_noreset_submit_new

# Example 16: IBM Parametrized No Reset Retrieve-Only
# #SBATCH --job-name=ibm_parametrized_noreset_retrieve_new
# ------------------------------

# Load modules if necessary (adapt to your cluster environment)
# module load python/3.10
source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env  

# Set environment variables for Qiskit Aer parallelization
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export QISKIT_AER_PARALLEL=True

# Ensure Python path includes project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/..

echo "Starting QPA Simulation on $(hostname)"
echo "Date: $(date)"
echo "CPUs: $SLURM_CPUS_PER_TASK"

# NOTE: This script assumes it is submitted from the 'scripts' directory.
# i.e., cd scripts && sbatch batch_job.slurm

# Example 1: Run AER with Dynamic Circuits (Standard)
# echo "Running AER Dynamic..."
# python3 -u ../main.py --backend aer --method dynamic --n 5 --k 2 --trials 3 --points 25  --shots 400000 --output ../data/results/k2/n5/n_trials3/results_aer_dynamic.csv

# Example 2: Run AER with Unrolled Circuits + Pauli Noise (Verification)
# echo "Running AER Unrolled (Verification)..."
# python3 -u ../main.py --backend aer --method unrolled --n 7 --k 2 --trials 3 --points 25 --shots 8000 --n-random 4000 --batch-size 25 --output ../data/results/k2/n7/n_trials3/results_aer_unrolled.csv

# Example 3: Run Fake Backend (Unrolled)
# echo "Running Fake Backend..."
# python3 -u ../main.py --backend fake --device ibm_boston --method unrolled --n 3 --k 2 --trials 3 --points 8 --shots 8000 --n-random 4000 --batch-size 200 --output ../data/results/k2/n3/n_trials3/results_fake_unparametrized.csv

# Example 4: Run IBM Backend (Post-Only)
# echo "Submitting IBM Jobs (Post-Only)..."
# python3 -u ../main.py --backend ibm --device ibm_boston --method unrolled --n 7 --k 2 --trials 3 --lambda-val 0.3 --shots 600 --n-random 300 --batch-size 100 --post-only --no-batchmode --output ../data/results/k2/n7/n_trials3/results_ibm_placeholder.csv

# Example 5: Retrieve IBM Results
# echo "Attempting to retrieve IBM results..."
# python3 -u ../retrieve_results.py --backend ibm --device ibm_boston --n 7 --k 2 --trials 3 --output ../data/results/k2/n7/n_trials3/results_ibm.csv

# Example 6: Retrieve AER Unrolled Results
# echo "Retrieving AER results..."
# python3 -u ../retrieve_results.py --backend aer --device aer_unrolled --n 3 --k 2 --trials 3 --output ../data/results/k2/n3/n_trials3/results_aer_unrolled.csv

# Example 7: Retrieve Fake Backend Results
# echo "Retrieving Fake Backend results..."
# python3 -u ../retrieve_results.py --backend fake --device ibm_boston --n 5 --k 2 --trials 3 --output ../data/results/k2/n5/n_trials3/results_fake.csv

# Example 8: Retrieve AER Dynamical Results
# echo "Retrieving AER results..."
# python3 -u ../retrieve_results.py --backend aer --device aer_dynamic --n 5 --k 2 --trials 3 --output ../data/results/k2/n5/n_trials3/results_aer_dynamic.csv

# Example 9: IBM Parameterized (New Method)
# This uses the new efficient PUB-based submission.
# --n-random: Total number of Pauli twirling instances to run.
# --batch-size: How many instances to pack into a SINGLE job (one PUB).
#               Set this high (e.g. 100-1000) to minimize queue overhead.
#               If n-random > batch-size, it will be split into multiple jobs.
# echo "Submitting IBM Parameterized Jobs..."
# python3 -u ../main.py --backend ibm --device ibm_boston --method parameterized --n 3 --k 2 --trials 3 --lambda-val 0.75 --shots 16000 --n-random 8000 --batch-size 4000 --post-only --no-batchmode --output ../data/results/k2/n3/n_trials3/results_ibm_param.csv

# Example 10: Retrieve IBM Parameterized Results
# Retrieves results for jobs tagged with 'parameterized' from a specific job directory.
# This is useful for checking the results of the new method specifically.
# echo "Retrieving IBM Parameterized Results..."
# python3 -u ../retrieve_results.py --backend ibm --device ibm_boston --n 3 --k 2 --trials 3 --filter-tag parameterized --output ../data/results/k2/n3/n_trials3/results_ibm_param_retrieved.csv


# Example 11: Fake Parameterized (New Method)
# This uses the new efficient PUB-based submission.
# --n-random: Total number of Pauli twirling instances to run.
# --batch-size: How many instances to pack into a SINGLE job (one PUB).
#               Set this high (e.g. 100-1000) to minimize queue overhead.
#               If n-random > batch-size, it will be split into multiple jobs.
# echo "Submitting Fake Parameterized Jobs..."
# python3 -u ../main.py --backend fake --device ibm_boston --method parameterized --n 5 --k 2 --trials 3 --points 8 --shots 8000 --n-random 4000 --batch-size 800 --no-batchmode --output ../data/results/k2/n5/n_trials3/results_fake_param.csv

# Example 12: AER Parameterized (New Method)
# This uses the new efficient PUB-based submission.
# --n-random: Total number of Pauli twirling instances to run.
# --batch-size: How many instances to pack into a SINGLE job (one PUB).
#               Set this high (e.g. 100-1000) to minimize queue overhead.
#               If n-random > batch-size, it will be split into multiple jobs.
# echo "Submitting AER Parameterized Jobs..."
# python3 -u ../main.py --backend aer --method parameterized --n 5 --k 2 --trials 3 --points 25 --shots 8000 --n-random 4000 --batch-size 2000 --no-batchmode --output ../data/results/k2/n5/n_trials3/results_aer_unrolled_param.csv

# Example 13: Retrieve AER Parameterized Results
# Retrieves results for jobs tagged with 'parameterized' from a specific job directory.
# This is useful for checking the results of the new method specifically.
# echo "Retrieving AER Parameterized Results..."
# python3 -u ../retrieve_results.py --backend aer --device aer_unrolled --n 5 --k 2 --trials 3 --filter-tag parameterized --output ../data/results/k2/n5/n_trials3/results_aer_unrolled_param_retrieved.csv

# Example 14: Fake Parameterized without resets (New Method)
# This uses the new efficient PUB-based submission.
# --n-random: Total number of Pauli twirling instances to run.
# --batch-size: How many instances to pack into a SINGLE job (one PUB).
#               Set this high (e.g. 100-1000) to minimize queue overhead.
#               If n-random > batch-size, it will be split into multiple jobs.
# echo "Submitting Fake Parameterized Jobs..."
# python3 -u ../main.py --backend fake --device ibm_boston --method parameterized --n 5 --k 2 --trials 3 --points 8 --shots 8000 --n-random 4000 --batch-size 2000 --no-batchmode --no-reset --output ../data/results/k2/n5/n_trials3/results_fake_param_no_resets.csv

# Example 15: IBM Parameterized No Reset (New Method)
# This uses the new efficient PUB-based submission.
# --n-random: Total number of Pauli twirling instances to run.
# --batch-size: How many instances to pack into a SINGLE job (one PUB).
#               Set this high (e.g. 100-1000) to minimize queue overhead.
#               If n-random > batch-size, it will be split into multiple jobs.
# echo "Submitting IBM Parameterized No Reset Jobs..."
# python3 -u ../main.py --backend ibm --device ibm_boston --method parameterized --n 3 --k 2 --trials 3 --lambda-val 0.75 --shots 24000 --n-random 12000 --batch-size 4000 --post-only --no-reset --no-batchmode --output ../data/results/k2/n3/n_trials3/results_ibm_param.csv


# Example 16: Retrieve IBM Parameterized No Reset Results
# Retrieves results for jobs tagged with 'parameterized' from a specific job directory.
# This is useful for checking the results of the new method specifically.
# echo "Retrieving IBM Parameterized Results..."
# python3 -u ../retrieve_results.py --backend ibm --device ibm_boston --n 3 --k 2 --trials 3 --filter-tag parameterized --no-reset --output ../data/results/k2/n3/n_trials3/results_ibm_param_retrieved_no_reset.csv


echo "Job Complete"
