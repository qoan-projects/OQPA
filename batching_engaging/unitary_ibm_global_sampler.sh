#!/bin/bash

K=2
SHOTS=135000
LAMBDA_MIN=0.0
LAMBDA_MAX=1.0
LAMBDA_STEPS=20
AERTESTING=true
FAKETESTING=false
for GATENOISE in 0; do
    for NRANDOM in 45000; do
        for nqpa in 0; do
            sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},LAMBDA_MIN=${LAMBDA_MIN},LAMBDA_MAX=${LAMBDA_MAX},LAMBDA_STEPS=${LAMBDA_STEPS},NRANDOM=${NRANDOM},GATENOISE=${GATENOISE},AERTESTING=${AERTESTING},FAKETESTING=${FAKETESTING} batching_engaging/unitary_ibm_global_sampler.slurm
        done
    done
done