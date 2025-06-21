#!/bin/bash

# Define constants
K=4
SHOTS=1024
EPS_VALUE=0.005  # <-- Fixed epsilon value
NQPA=1
INDEX=0

# Submit single job with fixed parameters
sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${NQPA},INDEX=${INDEX},EPS_VALUE=${EPS_VALUE} \
  /home/submit/caiosiq/qpa/purification/test_single_ryd_batch/ryd_copy.slurm
