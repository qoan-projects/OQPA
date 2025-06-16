#!/bin/bash

#!/bin/bash


SHOTS=102400
J=1.0
H=1.0
TROTTER=False
for T in 3.0; do
  for NQPA in 1; do
    for ntrot in 1 2 3 4 5 6 7 8 9 10 11 12 13; do
      sbatch --export=SHOTS=${SHOTS},STEPS=${ntrot},T=${T},J=${J},H=${H},NQPA=${NQPA},TROTTER=${TROTTER},SINGLECONTROL=${SINGLECONTROL} batching_engaging/new_fake_backend_engaging.slurm
    done
  done
done