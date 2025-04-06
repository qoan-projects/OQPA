#!/bin/bash

#!/bin/bash

K=3
SHOTS=102400
T=5.0
J=1.0
H=1.0
EPS_MIN=0.0
EPS_MAX=0.009
EPS_STEPS=40

for nqpa in 0 1 2; do
  for ntrot in 1 2 3 4 5; do
    sbatch --export=K=${K},SHOTS=${SHOTS},NQPA=${nqpa},STEPS=${ntrot},T=${T},J=${J},H=${H},EPS_MIN=${EPS_MIN},EPS_MAX=${EPS_MAX},EPS_STEPS=${EPS_STEPS} estimate.slurm
  done
done