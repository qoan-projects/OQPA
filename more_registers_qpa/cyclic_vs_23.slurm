#!/bin/bash
#SBATCH --job-name=cyclic_vs_23
#SBATCH --partition=mit_normal
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=128G
#SBATCH --time=02:59:59
#SBATCH --output=/home/caiosiq/OQPA-public/more_registers_qpa/logs/cyclic_vs_23_%j.out
#SBATCH --error=/home/caiosiq/OQPA-public/more_registers_qpa/logs/cyclic_vs_23_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=caiosiq@mit.edu

source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env

python /home/caiosiq/OQPA-public/more_registers_qpa/cyclic_vs_23.py
