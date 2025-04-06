#!/bin/bash
#SBATCH --job-name=estimation
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --array=0-39
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null

# === Setup task-specific log directory ===
TASK_TAG=k${K}_shots${SHOTS}_eps${EPS_MIN}-${EPS_MAX}_s${EPS_STEPS}
JOB_ID=${SLURM_ARRAY_JOB_ID}
EPS_INDEX=${SLURM_ARRAY_TASK_ID}
LOGDIR=logs/estimation_${JOB_ID}_${TASK_TAG}
mkdir -p ${LOGDIR}

exec > >(tee ${LOGDIR}/nqpa${NQPA}_ntrot${STEPS}_eps${EPS_INDEX}.out)
exec 2> >(tee ${LOGDIR}/nqpa${NQPA}_ntrot${STEPS}_eps${EPS_INDEX}.err >&2)


OUTDIR=data/estimation_${JOB_ID}_${TASK_TAG}
OUTFILE=nqpa${NQPA}_ntrot${STEPS}_eps${EPS_INDEX}.csv
mkdir -p ${OUTDIR}

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
echo "ε index            : ${EPS_INDEX}"
echo "ε sweep range      : ${EPS_MIN} → ${EPS_MAX}  (steps: ${EPS_STEPS})"
echo "Time t             : ${T}"
echo "Interaction J      : ${J}"
echo "Field h            : ${H}"
echo "Trotter steps      : ${STEPS}"
echo "==========================================="

python aer_estimation.py \
  --k ${K} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --epsilon-min ${EPS_MIN} \
  --epsilon-max ${EPS_MAX} \
  --epsilon-steps ${EPS_STEPS} \
  --epsilon-index ${EPS_INDEX} \
  --t ${T} \
  --J ${J} \
  --h ${H} \
  --steps ${STEPS} \
  --output ${OUTDIR}/${OUTFILE}
