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

TASK_TAG=k2_shots${SHOTS}
TAG=t${T}_J${J}_h${H}_ntrot${STEPS}
JOB_ID=${SLURM_JOB_ID}

LOGDIR=logs/new_fake_backend_estimation_${TASK_TAG}/nqpa${NQPA}
OUTDIR=data/new_fake_backend_estimation_${TASK_TAG}/nqpa${NQPA}
OUTFILE=${TAG}_${JOB_ID}.csv

mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}_${JOB_ID}.out")
exec 2> >(tee "${LOGDIR}/${TAG}_${JOB_ID}.err" >&2)

# === Detailed echo for traceability ===
echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${SLURM_JOB_ID}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""
echo "========== Simulation Parameters =========="
echo "Shots              : ${SHOTS}"
echo "Time t             : ${T}"
echo "Interaction J      : ${J}"
echo "Field h            : ${H}"
echo "Trotter steps      : ${STEPS}"
echo "NQPA               : ${NQPA}"
echo "TROTTER            : ${TROTTER}"
echo "==========================================="

python estimation_scripts/fakebackend_no_if_else_estimation.py \
  --shots ${SHOTS} \
  --t ${T} \
  --J ${J} \
  --h ${H} \
  --steps ${STEPS} \
  --output ${OUTDIR}/${OUTFILE}\
  --nqpa ${NQPA}\
  --trotter ${TROTTER}\
