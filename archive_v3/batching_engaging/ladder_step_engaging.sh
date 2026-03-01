#!/bin/bash

#!/bin/bash


SHOTS=1024
for NQPA in 0 1; do
    sbatch --export=SHOTS=${SHOTS},NQPA=${NQPA} batching_engaging/ladder_step_engaging.slurm
done