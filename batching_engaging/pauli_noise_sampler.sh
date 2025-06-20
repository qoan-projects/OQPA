#!/bin/bash

K=2
SHOTS=10240000
EPS_MIN=0.0
EPS_MAX=0.1
EPS_STEPS=41
NRANDOM=1000
GATENOISE=0.05
for nqpa in 0 1; do
    sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS},NRANDOM=${NRANDOM},GATENOISE=${GATENOISE} batching_engaging/pauli_noise_sampler.slurm
done