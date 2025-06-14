#!/bin/bash

#!/bin/bash

K=3
SHOTS=1024
J=1.0
H=1.0

for T in 1.0 2.0, 3.0; do
  for ntrot in 1 2 3 4 5; do
    sbatch --export=K=${K},SHOTS=${SHOTS},STEPS=${ntrot},T=${T},J=${J},H=${H} fake_backend.slurm
  done
done