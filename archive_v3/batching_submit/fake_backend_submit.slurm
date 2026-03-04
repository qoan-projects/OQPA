#!/bin/bash
#SBATCH --job-name=fake_backend
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
conda activate qpa_env 
TASK_TAG=k${K}_shots${SHOTS}
TAG=t${T}_J${J}_h${H}_ntrot${STEPS}
JOB_ID=${SLURM_JOB_ID}

LOGDIR=logs/fake_backend_estimation_${TASK_TAG}/nqpa${NQPA}
OUTDIR=data/fake_backend_estimation_${TASK_TAG}/nqpa${NQPA}
OUTFILE=${TAG}_${JOB_ID}.csv

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
echo "NQPA               : ${NQPA}"
echo "TROTTER            : ${TROTTER}"
echo "SINGLE CONTROL     : ${SINGLECONTROL}"
echo "==========================================="

python estimation_scripts/fakebackend_estimation.py \
  --k ${K} \
  --shots ${SHOTS} \
  --t ${T} \
  --J ${J} \
  --h ${H} \
  --steps ${STEPS} \
  --output ${OUTDIR}/${OUTFILE}
