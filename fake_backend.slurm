#!/bin/bash
#SBATCH --job-name=estimation
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=80
#SBATCH --mem=128G
#SBATCH --time=23:59:00
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-user=caiosiq@mit.edu

# === Setup task-specific log directory ===

source ~/.bashrc
conda activate qpa_env  # or whatever your environment name is
TASK_TAG=k${K}_shots${SHOTS}_ID
TAG=${SLURM_JOB_ID}_ntrot${STEPS}_t${T}_J${J}_h${H}

LOGDIR=logs/fake_backend_estimation_${TASK_TAG}/${TAG}
OUTDIR=data/fake_backend_estimation_${TASK_TAG}/${TAG}
OUTFILE=${TAG}.csv

mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}.out")
exec 2> >(tee "${LOGDIR}/${TAG}.err" >&2)

# === Detailed echo for traceability ===
echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${SLURM_JOB_ID}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""
echo "========== Simulation Parameters =========="
echo "Qubits per reg (k) : ${K}"
echo "Shots              : ${SHOTS}"
echo "Time t             : ${T}"
echo "Interaction J      : ${J}"
echo "Field h            : ${H}"
echo "Trotter steps      : ${STEPS}"
echo "==========================================="

python estimation_scripts/fakebackend_estimation.py \
  --k ${K} \
  --shots ${SHOTS} \
  --t ${T} \
  --J ${J} \
  --h ${H} \
  --steps ${STEPS} \
  --output ${OUTDIR}/${OUTFILE}
