#!/bin/bash
#SBATCH --job-name=estimation_k3_s102400_nqpa2_ntrot5
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --array=0-39
#SBATCH --output=logs/estimation_k3_s102400_nqpa2_ntrot5_%A_%a.out
#SBATCH --error=logs/estimation_k3_s102400_nqpa2_ntrot5_%A_%a.err

echo "Running ε index: $SLURM_ARRAY_TASK_ID on node $(hostname)"
echo "Using $SLURM_CPUS_ON_NODE CPUs"

# Define parameters
K=3
SHOTS=102400
NQPA=2
EPS_MIN=0.0
EPS_MAX=0.009
EPS_STEPS=40
EPS_INDEX=$SLURM_ARRAY_TASK_ID

T=5.0
J=1.0
H=1.0
STEPS=5

OUTDIR=data/estimation_k${K}_shots${SHOTS}_nqpa${NQPA}_ntrot${STEPS}
OUTFILE=fidelity_epsilon${EPS_MIN}-${EPS_MAX}_steps${EPS_STEPS}_eps${EPS_INDEX}.csv

mkdir -p ${OUTDIR} logs

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