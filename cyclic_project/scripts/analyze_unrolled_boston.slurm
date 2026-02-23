#!/bin/bash 
#SBATCH --job-name=analyze_unrolled_boston
#SBATCH --output=../data/logs/%x_%j.out
#SBATCH --error=../data/logs/%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=256G
#SBATCH --cpus-per-task=10
#SBATCH --time=6:00:00
#SBATCH --partition=mit_normal_gpu

# Load modules
source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env  

# Ensure Python path includes project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/..

echo "Starting Unrolled Analysis on $(hostname)"
echo "Date: $(date)"

# Run the unrolled analysis script
python3 -u analyze_unrolled_boston.py

echo "Job Complete"
