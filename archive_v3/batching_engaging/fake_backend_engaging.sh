#!/bin/bash

#!/bin/bash


SHOTS=1024
J=1.0
H=1.0
TROTTER=false
SINGLECONTROL=true
for K in 2 3; do
  for T in 3.0; do
    for NQPA in 0; do
      for ntrot in 1 2 3 4 5 6 7 8 9 10 11 12 13; do
        sbatch --export=K=${K},SHOTS=${SHOTS},STEPS=${ntrot},T=${T},J=${J},H=${H},NQPA=${NQPA},TROTTER=${TROTTER},SINGLECONTROL=${SINGLECONTROL} batching_engaging/fake_backend_engaging.slurm
      done
    done
  done
done
