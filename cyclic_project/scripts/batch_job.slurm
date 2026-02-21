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
#SBATCH --job-name=fake_run_new

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
echo "Running Fake Backend..."
python3 -u ../main.py --backend fake --device ibm_boston --method unrolled --n 7 --k 2 --trials 3 --points 8 --shots 100 --n-random 50 --batch-size 50 --output ../data/results/k2/n7/n_trials3/results_fake_s100_r50_b50.csv

# Example 4: Run IBM Backend (Post-Only)
# echo "Submitting IBM Jobs (Post-Only)..."
# python3 -u ../main.py --backend ibm --device ibm_boston --method unrolled --n 3 --k 2 --trials 3 --points 25 --shots 4000 --n-random 800 --batch-size 200 --post-only --output ../data/results/k2/n3/n_trials3/results_ibm_placeholder.csv

# Example 5: Retrieve IBM Results
# echo "Attempting to retrieve IBM results..."
# python3 -u ../retrieve_results.py --backend ibm --device ibm_boston --n 5 --k 2 --trials 3 --output ../data/results/k2/n5/n_trials3/results_ibm.csv

# Example 6: Retrieve AER Unrolled Results
# echo "Retrieving AER results..."
# python3 -u ../retrieve_results.py --backend aer --device aer_unrolled --n 3 --k 2 --trials 3 --output ../data/results/k2/n3/n_trials3/results_aer_unrolled.csv

# Example 7: Retrieve Fake Backend Results
# echo "Retrieving Fake Backend results..."
# python3 -u ../retrieve_results.py --backend fake --device ibm_boston --n 5 --k 2 --trials 3 --output ../data/results/k2/n5/n_trials3/results_fake.csv

# Example 8: Retrieve AER Dynamical Results
# echo "Retrieving AER results..."
# python3 -u ../retrieve_results.py --backend aer --device aer_dynamic --n 5 --k 2 --trials 3 --output ../data/results/k2/n5/n_trials3/results_aer_dynamic.csv

echo "Job Complete"
