#!/bin/bash
#SBATCH --job-name=pauli_noise
#SBATCH --partition=mit_normal
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --array=0-40
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-type=ALL
#SBATCH --mail-user=caiosiq@mit.edu

source ~/.bashrc
module load miniforge/24.3.0-0
conda activate qpa_env  # or whatever your environment name is

# === Setup task-specific log directory ===
TASK_TAG=k${K}_shots${SHOTS}_eps${EPS_MIN}-${EPS_MAX}_s${EPS_STEPS}_r${NRANDOM}_g${GATENOISE}
JOB_ID=${SLURM_ARRAY_JOB_ID}  
EPS_INDEX=${SLURM_ARRAY_TASK_ID}
TAG=nqpa${NQPA}_eps${EPS_INDEX}

LOGDIR=logs/pauli_noise_sampler_${TASK_TAG}/nqpa${NQPA}
OUTDIR=shared_data/pauli_noise_sampler/simulation_outputs/pauli_noise_sampler_${TASK_TAG}/nqpa${NQPA}
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
echo "SLURM Array Task ID: ${EPS_INDEX}"
echo "CPUs per node      : ${SLURM_CPUS_ON_NODE}"
echo ""
echo "========== Simulation Parameters =========="
echo "Qubits per reg (k) : ${K}"
echo "Shots              : ${SHOTS}"
echo "QPA rounds (NQPA)  : ${NQPA}"
echo "ε index            : ${EPS_INDEX}"
echo "ε sweep range      : ${EPS_MIN} → ${EPS_MAX}  (steps: ${EPS_STEPS})"
echo "Random circuits    : ${NRANDOM}"
echo "Gate noise         : ${GATENOISE}"
echo "==========================================="

python sampler_scripts/pauli_noise_gates_sampler.py \
  --k ${K} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --epsilon-min ${EPS_MIN} \
  --epsilon-max ${EPS_MAX} \
  --epsilon-steps ${EPS_STEPS} \
  --epsilon-index ${EPS_INDEX} \
  --nrandom ${NRANDOM} \
  --gatenoise ${GATENOISE} \
  --output ${OUTDIR}/${OUTFILE}
