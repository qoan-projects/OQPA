#!/bin/bash
#SBATCH --job-name=ryd-sim
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=00:10:00
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-type=ALL
#SBATCH --mail-user=ladmon@mit.edu

# ============================================================================
# This SLURM job will save logs and data to:
#
#   LOGDIR = logs/ryd_test_k${K}_shots${SHOTS}_eps${EPS}_index${INDEX}/${SLURM_JOB_ID}
#   OUTDIR = data/ryd_test_k${K}_shots${SHOTS}_eps${EPS}_index${INDEX}/${SLURM_JOB_ID}
#   OUTFILE = ${OUTDIR}/nqpa${NQPA}_eps${EPS}.csv
#
# These are determined by: K, SHOTS, EPS, INDEX, NQPA
# ============================================================================

# === Load conda environment ===
source ~/.bashrc
conda activate qpa_env

# === Setup paths and tags ===
TASK_TAG=k${K}_shots${SHOTS}_eps${EPS}_index${INDEX}
JOB_ID=${SLURM_JOB_ID}
TAG=nqpa${NQPA}_eps${EPS}

LOGDIR=logs/ryd_test_${TASK_TAG}/${TAG}
OUTDIR=data/ryd_test_${TASK_TAG}/${TAG}
OUTFILE=${JOB_ID}.csv

INPUT_STATES_FILE=/home/submit/caiosiq/qpa/purification/shared_data/ryd_estimations/all_states.npz
EXACT_STATE_FILE=/home/submit/caiosiq/qpa/purification/shared_data/ryd_estimations/exact_state.npz

mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}.out")
exec 2> >(tee "${LOGDIR}/${TAG}.err" >&2)

echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${JOB_ID}"
echo ""
echo "========== Simulation Parameters =========="
echo "Qubits per reg (k) : ${K}"
echo "Shots              : ${SHOTS}"
echo "QPA rounds (NQPA)  : ${NQPA}"
echo "State index        : ${INDEX}"
echo "Epsilon (noise)    : ${EPS_VALUE}"
echo "Using exact state  : ${EXACT_STATE_FILE}"
echo "==========================================="

# === Run estimation script ===
python /home/submit/caiosiq/qpa/purification/test_single_ryd_batch/custom_state_estimation_copy.py \
  --k ${K} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --epsilon ${EPS_VALUE} \
  --state-index ${INDEX} \
  --datafile ${INPUT_STATES_FILE} \
  --exact_state_file ${EXACT_STATE_FILE} \
  --output ${OUTDIR}/${OUTFILE}
