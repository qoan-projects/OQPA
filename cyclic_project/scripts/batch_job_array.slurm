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

# Example: Run Fake Backend (Unrolled) with Parallel Lambda
# We disable internal batching (batch-size -1) since we are parallelizing over lambdas
# and want to finish this single lambda as fast as possible.
echo "Running QPA for Task ID: $SLURM_ARRAY_TASK_ID"

python3 ../main.py \
    --backend fake \
    --device ibm_marrakesh \
    --method unrolled \
    --n 5 \
    --k 2 \
    --trials 3 \
    --points $POINTS \
    --shots 2000 \
    --n-random 2000 \
    --batch-size -1 \
    --slurm-task-id $SLURM_ARRAY_TASK_ID \
    --output ../data/results/array_test/results.csv

echo "Task $SLURM_ARRAY_TASK_ID Complete"

# Note: After all tasks complete, run:
# python3 scripts/merge_results.py --pattern "../data/results/array_test/results_task*.csv" --output "../data/results/array_test/final_results.csv"
