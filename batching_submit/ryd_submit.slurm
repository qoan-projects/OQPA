#!/bin/bash
#SBATCH --job-name=ryd-sim
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-type=ALL
#SBATCH --mail-user=caiosiq@mit.edu

# === Setup naming variables ===
# K            = Qubits per register
# SHOTS        = Number of shots per circuit execution
# EPS_MIN/MAX  = Range of epsilon noise values
# EPS_STEPS    = Number of epsilon steps in the sweep
# INDEX        = Which eigenvector combination to simulate
# NQPA         = Number of QPA purification rounds
# STEPS        = Number of trotter steps (optional label)


# === Load environment ===
source ~/.bashrc      # Load conda initialization (you must have done `conda init bash`)
conda activate qpa_env  # Activate the qpa_env conda environment

# === Setup task-specific log directory ===
TASK_TAG=k${K}_shots${SHOTS}_eps${EPS_MIN}-${EPS_MAX}_s${EPS_STEPS}
JOB_ID=${SLURM_ARRAY_JOB_ID}
EPS_INDEX=${SLURM_ARRAY_TASK_ID}
TAG=eps${EPS_INDEX}_${SLURM_ARRAY_JOB_ID}


# === Directory/file structure ===
# Final output will be saved at:
#   → data/ryd_estimation_k${K}_shots${SHOTS}_eps${EPS_MIN}-${EPS_MAX}_s${EPS_STEPS}/nqpa${NQPA}/${JOB_ID}_index${INDEX}/${TAG}.csv
# Logs will be saved at:
#   → logs/ryd_estimation_k${K}_shots${SHOTS}_eps${EPS_MIN}-${EPS_MAX}_s${EPS_STEPS}/index${INDEX}/nqpa${NQPA}/${TAG}.out / .err
LOGDIR=logs/ryd_estimation_${TASK_TAG}/index${INDEX}/nqpa${NQPA}
OUTDIR=data/ryd_estimation_${TASK_TAG}/index${INDEX}/nqpa${NQPA}
OUTFILE=${TAG}.csv
INPUT_STATES_FILE=/home/submit/caiosiq/qpa/purification/shared_data/ryd_estimations/all_states.npz
EXACT_STATE_FILE=/home/submit/caiosiq/qpa/purification/shared_data/ryd_estimations/exact_state.npz


mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}.out")
exec 2> >(tee "${LOGDIR}/${TAG}.err" >&2)

# === Detailed echo for traceability ===
echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${JOB_ID}"
echo "SLURM Array Task ID: ${EPS_INDEX}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""
echo "========== Simulation Parameters =========="
echo "Qubits per reg (k) : ${K}"
echo "Shots              : ${SHOTS}"
echo "QPA rounds (NQPA)  : ${NQPA}"
echo "State index        : ${INDEX}"
echo "ε index            : ${EPS_INDEX}"
echo "ε sweep range      : ${EPS_MIN} → ${EPS_MAX}  (steps: ${EPS_STEPS})"
echo "Using exact state  : ${EXACT_STATE_FILE}"

echo "==========================================="

python estimation_scripts/custom_state_estimation.py \
  --k ${K} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --epsilon-min ${EPS_MIN} \
  --epsilon-max ${EPS_MAX} \
  --epsilon-steps ${EPS_STEPS} \
  --epsilon-index ${EPS_INDEX} \
  --state-index ${INDEX} \
  --datafile ${INPUT_STATES_FILE} \
  --exact_state_file ${EXACT_STATE_FILE} \
  --output ${OUTDIR}/${OUTFILE}
