#!/bin/bash

K=4
SHOTS=102400
EPS_MIN=0.0
EPS_MAX=0.01
EPS_STEPS=41

for index in 0 1 2 3 4 5 6 7; do
  for nqpa in 2; do
    sbatch --array=0-$(($EPS_STEPS - 1)) \
      --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},INDEX=${index},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS} \
      batching_engaging/ryd_engaging.slurm
  done
done
