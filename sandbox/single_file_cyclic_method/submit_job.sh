#!/bin/bash
#SBATCH --job-name=qpa_scaling
#SBATCH --array=4-6
#SBATCH --partition=mit_normal
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=256G
#SBATCH --time=08:59:59
#SBATCH --output=logs/qpa_%a.out
#SBATCH --error=logs/qpa_%a.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=caiosiq@mit.edu


# Mapping array index to N values
# Index 0 -> N=3
# Index 1 -> N=5
# Index 2 -> N=7
# Index 3 -> N=9
# NS=(3 5 7 9)


NS=(3 5 7 9 11 13 15)
NWORKERS=(40 40 40 20 1 1 1)
CURRENT_N=${NS[$SLURM_ARRAY_TASK_ID]}
CURRENT_NWORKERS=${NWORKERS[$SLURM_ARRAY_TASK_ID]}
echo "Running QPA Simulation for N=$CURRENT_N on $(hostname)"

# Make sure log dir exists
mkdir -p logs

# Activate your environment
source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env

# Run the engine
# Pass the number of allocated CPUs to the python script
python qpa_engine.py \
    --n $CURRENT_N \
    --k 1 \
    --trials 4 \
    --shots 400000 \
    --points 25 \
    --workers $CURRENT_NWORKERS

echo "Finished N=$CURRENT_N"