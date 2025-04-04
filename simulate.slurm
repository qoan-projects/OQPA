#!/bin/bash
#SBATCH --job-name=qpa_sim_d6_s10240_nqpa1
#SBATCH --partition=submit-gpu-a30
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-gpu=1
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --array=0-39
#SBATCH --output=logs/qpa_sim_d6_s10240_nqpa1_%A_%a.out
#SBATCH --error=logs/qpa_sim_d6_s10240_nqpa1_%A_%a.err

# CUDA setup (optional)
echo "Running λ index: $SLURM_ARRAY_TASK_ID on node $(hostname)"
echo "Using GPU(s):"
nvidia-smi --query-gpu=name,index,memory.total --format=csv

export CUDA_ROOT=/usr/local/cuda
export PATH=$CUDA_ROOT/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_ROOT/lib64:$LD_LIBRARY_PATH

# Define params
D=6
SHOTS=10240
NQPA=1
LAM_MIN=0.0
LAM_MAX=1.0
LAM_STEPS=40
LAMBDA_INDEX=$SLURM_ARRAY_TASK_ID

# Define output pat
OUTDIR=data/d${D}_shots${SHOTS}_nqpa${NQPA}
OUTFILE=fidelity_lambda${LAM_MIN}-${LAM_MAX}_steps${LAM_STEPS}_lam${LAMBDA_INDEX}.csv

mkdir -p ${OUTDIR} logs

# Run the simulation
python aer_simulation.py \
  --d ${D} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --lambda-min ${LAM_MIN} \
  --lambda-max ${LAM_MAX} \
  --lambda-steps ${LAM_STEPS} \
  --lambda-index ${LAMBDA_INDEX} \
  --output ${OUTDIR}/${OUTFILE}
