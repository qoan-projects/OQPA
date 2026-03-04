#!/bin/bash
#SBATCH --job-name=fake_backend
#SBATCH --partition=mit_normal
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=80
#SBATCH --mem=128G
#SBATCH --time=11:59:00
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-user=caiosiq@mit.edu

# === Setup task-specific log directory ===

source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env  # or whatever your environment name is

TASK_TAG=k${K}_shots${SHOTS}
TAG=test
JOB_ID=${SLURM_JOB_ID}

LOGDIR=logs/fidelity_comparison

mkdir -p "${LOGDIR}"

exec > >(tee "${LOGDIR}/${TAG}.out")
exec 2> >(tee "${LOGDIR}/${TAG}.err" >&2)


# === Detailed echo for traceability ===
echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${SLURM_JOB_ID}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""

python estimation_scripts/no_if_else_fidelity_comparison.py