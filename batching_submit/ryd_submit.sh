#!/bin/bash

K=4
SHOTS=1024
EPS_MIN=0.0
EPS_MAX=0.1
EPS_STEPS=2

for index in 0; do
  for nqpa in 0 1 2; do
    sbatch --array=0-$(($EPS_STEPS - 1)) \
      --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},INDEX=${index},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS} \
      batching_submit/ryd_submit.slurm
  done
done
