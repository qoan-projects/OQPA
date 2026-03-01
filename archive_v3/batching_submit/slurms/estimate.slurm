#!/bin/bash
#SBATCH --job-name=estimation_simple
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null

# Simple SLURM wrapper for the aer estimator (placeholders kept simple)

# --- Task variables (set these when submitting or export before sbatch) ---
K=${K:-3}
SHOTS=${SHOTS:-10240}
STEPS=${STEPS:-10}
EPS_MIN=${EPS_MIN:-0.0}
EPS_MAX=${EPS_MAX:-0.1}
EPS_STEPS=${EPS_STEPS:-11}
N=${N:-3}
TRIALS=${TRIALS:-1}
METHOD=${METHOD:-unrolled}

JOB_ID=${SLURM_JOB_ID:-local}
TAG=k${K}_s${STEPS}_eps${EPS_MIN}-${EPS_MAX}

LOGDIR=logs/estimation_${TAG}/${JOB_ID}
OUTDIR=data/aer_estimation/${TAG}/${JOB_ID}
OUTFILE=${TAG}.csv

mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}.out")
exec 2> >(tee "${LOGDIR}/${TAG}.err" >&2)

echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${JOB_ID}"

echo "Running estimator with: K=${K}, STEPS=${STEPS}, EPS range=${EPS_MIN}-${EPS_MAX} (steps ${EPS_STEPS})"

# Run the estimator (uses PYTHONPATH to include cyclic_project)
PYTHONPATH=cyclic_project python3 cyclic_project/aer_trotter_estimation_scripts/aer_estimation_arbitrary_inputs.py \
  --k ${K} \
  --steps ${STEPS} \
  --epsilon-min ${EPS_MIN} \
  --epsilon-max ${EPS_MAX} \
  --epsilon-steps ${EPS_STEPS} \
  --n ${N} \
  --trials ${TRIALS} \
  --method ${METHOD} \
  --shots ${SHOTS} \
  --output ${OUTDIR}/${OUTFILE}
