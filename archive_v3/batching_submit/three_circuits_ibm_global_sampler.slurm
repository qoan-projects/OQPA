#!/bin/bash
#SBATCH --job-name=three_circuits_ibm_global_sampler
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=128G
#SBATCH --time=23:59:00
#SBATCH --array=0-19
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-type=ALL
#SBATCH --mail-user=caiosiq@mit.edu

source ~/.bashrc
conda activate qpa_env 

# === Setup task-specific log directory ===
TASK_TAG=k${K}_shots${SHOTS}_lambda${LAMBDA_MIN}-${LAMBDA_MAX}_s${LAMBDA_STEPS}_r${NRANDOM}_g${GATENOISE}_aer${AERTESTING}_fake${FAKETESTING}
JOB_ID=${SLURM_ARRAY_JOB_ID}  
LAMBDA_INDEX=${SLURM_ARRAY_TASK_ID}
TAG=nqpa${NQPA}_lambda${LAMBDA_INDEX}

LOGDIR=logs/three_circuits_ibm_global_sampler_${TASK_TAG}/nqpa${NQPA}
OUTDIR=data/three_circuits_ibm_global_sampler/simulation_outputs/three_circuits_ibm_global_sampler_${TASK_TAG}/nqpa${NQPA}
OUTFILE=${TAG}_${JOB_ID}.csv

mkdir -p "${LOGDIR}"
mkdir -p "${OUTDIR}"

exec > >(tee "${LOGDIR}/${TAG}_${JOB_ID}.out")
exec 2> >(tee "${LOGDIR}/${TAG}_${JOB_ID}.err" >&2)

# === Detailed echo for traceability ===
echo "========== SLURM Job Info =========="
echo "Hostname           : $(hostname)"
echo "Date               : $(date)"
echo "SLURM Job ID       : ${JOB_ID}"
echo "SLURM Array Task ID: ${LAMBDA_INDEX}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""
echo "========== Simulation Parameters =========="
echo "Qubits per reg (k) : ${K}"
echo "Shots              : ${SHOTS}"
echo "QPA rounds (NQPA)  : ${NQPA}"
echo "λ index            : ${LAMBDA_INDEX}"
echo "λ sweep range      : ${LAMBDA_MIN} → ${LAMBDA_MAX}  (steps: ${LAMBDA_STEPS})"
echo "Random circuits    : ${NRANDOM}"
echo "Gate noise         : ${GATENOISE}"
echo "Aer testing        : ${AERTESTING}"
echo "Fake testing       : ${FAKETESTING}"
echo "==========================================="

python ibm_global_sampler_scripts/three_circuits_ibm_global_sampler.py \
  --k ${K} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --lambda-min ${LAMBDA_MIN} \
  --lambda-max ${LAMBDA_MAX} \
  --lambda-steps ${LAMBDA_STEPS} \
  --lambda-index ${LAMBDA_INDEX} \
  --nrandom ${NRANDOM} \
  --gatenoise ${GATENOISE} \
  --aertesting ${AERTESTING} \
  --faketesting ${FAKETESTING} \
  --output ${OUTDIR}/${OUTFILE}
