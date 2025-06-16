#!/bin/bash

K=2
SHOTS=10240
T=3.0
J=1.0
H=1.0
EPS_MIN=0.0
EPS_MAX=0.1
EPS_STEPS=20

for nqpa in 0 1 2 3; do
  for ntrot in 5; do
    sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},STEPS=${ntrot},T=${T},J=${J},H=${H},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS} batching_engaging/estimate.slurm
  done
done