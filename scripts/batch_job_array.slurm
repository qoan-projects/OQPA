#!/bin/bash
#SBATCH --job-name=qpa_array
#SBATCH --output=../data/logs/qpa_array_%A_%a.out
#SBATCH --error=../data/logs/qpa_array_%A_%a.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=258G
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --partition=mit_normal
#SBATCH --array=0-24  # Update this to match (points - 1)

# Load environment
source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export QISKIT_AER_PARALLEL=True

echo "Starting Array Task $SLURM_ARRAY_TASK_ID on $(hostname)"
echo "Date: $(date)"

# Run for a SINGLE lambda (determined by array task ID)
# Set --points to match the array size + 1 (e.g. 0-24 means 25 points)
POINTS=25

# Example: Run Aer Backend (Dynamic) sharded over lambda points
echo "Running Aer Dynamic for Task ID: $SLURM_ARRAY_TASK_ID"

python3 ../main.py \
    --backend aer \
    --method dynamic \
    --n 5 \
    --k 2 \
    --trials 3 \
    --points $POINTS \
    --shots 400000 \
    --slurm-task-id $SLURM_ARRAY_TASK_ID \
    --output ../data/results/k2/n5/n_trials3/array_aer_dynamic_task_${SLURM_ARRAY_TASK_ID}.csv

echo "Task $SLURM_ARRAY_TASK_ID Complete"

# Note: After all tasks complete, merge per-task CSVs:
# python3 scripts/merge_results.py --pattern "../data/results/k2/n5/n_trials3/array_aer_dynamic_task_*.csv" --output "../data/results/k2/n5/n_trials3/results_aer_dynamic_merged.csv"
