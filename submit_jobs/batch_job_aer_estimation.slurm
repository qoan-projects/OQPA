#!/bin/bash
#SBATCH --job-name=aer_est_sweep
#SBATCH --output=aer_trotter_data/logs/%x_%A_%a.out
#SBATCH --error=aer_trotter_data/logs/%x_%A_%a.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=12:00:00
#SBATCH --partition=mit_normal
#SBATCH --array=0-109  # 11 epsilons * 10 steps = 110 jobs

# Load modules and environment
source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env

# Set PYTHONPATH to include project root (assuming run from submit_jobs/)
export PYTHONPATH=$PYTHONPATH:$(pwd)/..

echo "Starting AER Estimation Job Array Task $SLURM_ARRAY_TASK_ID on $(hostname)"
echo "Date: $(date)"

# Define Parameter Arrays
# Epsilon: 0 to 0.005 step 0.0005 (11 values)
EPSILONS=(0.0 0.0005 0.001 0.0015 0.002 0.0025 0.003 0.0035 0.004 0.0045 0.005)

# Steps: 2 to 20 step 2 (10 values)
STEPS_LIST=(2 4 6 8 10 12 14 16 18 20)

# Calculate indices for 2D grid sweep
NUM_STEPS=${#STEPS_LIST[@]}
NUM_EPS=${#EPSILONS[@]}

# Map Task ID to (Epsilon, Steps) pair
# EPS_IDX changes every NUM_STEPS tasks (Slow Axis)
EPS_IDX=$((SLURM_ARRAY_TASK_ID / NUM_STEPS))
# STEPS_IDX cycles 0..NUM_STEPS-1 (Fast Axis)
STEPS_IDX=$((SLURM_ARRAY_TASK_ID % NUM_STEPS))

# Safety check
if [ $EPS_IDX -ge $NUM_EPS ]; then
    echo "Error: Task ID $SLURM_ARRAY_TASK_ID out of range for parameter grid (Max Eps Index: $((NUM_EPS-1)))."
    exit 1
fi

EPS=${EPSILONS[$EPS_IDX]}
STEPS=${STEPS_LIST[$STEPS_IDX]}

echo "Running with Parameters: Epsilon=$EPS, Steps=$STEPS"

# Define Output Directory
OUT_DIR="aer_trotter_data/results"
# Ensure the base results directory exists; the python script will create subdirectories
mkdir -p $OUT_DIR

# Run the script
SCRIPT_PATH="aer_trotter_estimation_scripts/aer_estimation.py"

python3 -u $SCRIPT_PATH \
    --epsilon $EPS \
    --steps $STEPS \
    --output $OUT_DIR \
    --k 2 \
    --n 1 \
    --trials 1 \
    --shots 50000 \
    --t 1.0 \
    --J 1.0 \
    --h 1.0 \
    --method dynamic \
    --noise depolarizing

echo "Task $SLURM_ARRAY_TASK_ID Complete"
