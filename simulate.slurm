#!/bin/bash
#SBATCH --job-name=qpa_sim_d4_s10240
#SBATCH --partition=submit-gpu-a30
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-gpu=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/qpa_sim_d4_s10240_%j.out
#SBATCH --error=logs/qpa_sim_d4_s10240_%j.err

# CUDA setup (optional)
export CUDA_ROOT=/usr/local/cuda
export PATH=$CUDA_ROOT/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_ROOT/lib64:$LD_LIBRARY_PATH

# Define params
D=4
SHOTS=10240
NQPA=1
LAM_MIN=0.0
LAM_MAX=1.0
LAM_STEPS=20

# Define output path
OUTDIR=data/d${D}_shots${SHOTS}_nqpa${NQPA}
OUTFILE=fidelity_lambda${LAM_MIN}-${LAM_MAX}_steps${LAM_STEPS}.csv

mkdir -p ${OUTDIR} logs

# Run the simulation
python aer_simulation.py \
  --d ${D} \
  --shots ${SHOTS} \
  --nqpa ${NQPA} \
  --lambda-min ${LAM_MIN} \
  --lambda-max ${LAM_MAX} \
  --lambda-steps ${LAM_STEPS} \
  --output ${OUTDIR}/${OUTFILE}