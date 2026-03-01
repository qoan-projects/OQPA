#!/bin/bash

K=4
SHOTS=102400
EPS_MIN=0.0
EPS_MAX=0.001
EPS_STEPS=41

for index in $(seq 0 124); do
  for nqpa in 1; do
    sbatch --array=0-$(($EPS_STEPS - 1)) \
      --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},INDEX=${index},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS} \
      batching_submit/ryd_submit.slurm
  done
done
