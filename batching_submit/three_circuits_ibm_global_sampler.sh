#!/bin/bash

K=2
SHOTS=4000
LAMBDA_MIN=0.0
LAMBDA_MAX=1.0
LAMBDA_STEPS=20
AERTESTING=false
FAKETESTING=true
for GATENOISE in 0.0; do
    for NRANDOM in 3000; do
        for nqpa in 3; do
            sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},LAMBDA_MIN=${LAMBDA_MIN},LAMBDA_MAX=${LAMBDA_MAX},LAMBDA_STEPS=${LAMBDA_STEPS},NRANDOM=${NRANDOM},GATENOISE=${GATENOISE},AERTESTING=${AERTESTING},FAKETESTING=${FAKETESTING} batching_submit/three_circuits_ibm_global_sampler.slurm
        done
    done
done