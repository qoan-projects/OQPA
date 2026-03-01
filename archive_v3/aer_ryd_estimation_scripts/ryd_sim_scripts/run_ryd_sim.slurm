#!/bin/bash
#SBATCH --job-name=estimation
#SBATCH --partition=submit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --array=0-999
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --mail-type=ALL
#SBATCH --mail-user=ladmon@mit.edu

# ----- Parameter grid (inline) ------------------------------------
OMEGAS=(2.82 2.84 2.86 2.88 2.9 2.92 2.94 2.96 2.98 3)         # Ω / 2π in MHz
DELTAS=(4.2 4.4 4.6 4.8 5 5.2 5.4 5.6 5.8 6)             # Δ / 2π in MHz
TTOTS=(1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8 1.9 1)               # T_tot in units of 1e-6 s

# Total combinations
NUM_OMEGAS=${#OMEGAS[@]}
NUM_DELTAS=${#DELTAS[@]}
NUM_TTOTS=${#TTOTS[@]}

# Compute index into each grid
IDX=$SLURM_ARRAY_TASK_ID

i_omega=$(( IDX / (NUM_DELTAS * NUM_TTOTS) ))
i_delta=$(( (IDX / NUM_TTOTS) % NUM_DELTAS ))
i_ttot=$(( IDX % NUM_TTOTS ))

OM=${OMEGAS[$i_omega]}
DELTA=${DELTAS[$i_delta]}
Ttot=${TTOTS[$i_ttot]}

# ---- Constants ----
k=4
V0=40
T2=6

# ---- Derived time splits ----
Tup=$(python -c "print(${Ttot}*0.33)")
Ts=$(python  -c "print(${Ttot}*0.34)")
Tdown=$Tup

# ---- Job ID + Log Tagging ----
TAG="k${k}_V${V0}MHz_Om${OM}MHz_D${DELTA}MHz_T${Ttot}us"
JOB_ID=${SLURM_ARRAY_JOB_ID}
TASK_ID=${SLURM_ARRAY_TASK_ID}

LOGDIR="../logs/fidelity_${JOB_ID}"
DATADIR="../data"
mkdir -p "${LOGDIR}" "${DATADIR}/rho" "${DATADIR}/fidelity"

exec  > >(tee  "${LOGDIR}/${TAG}.out")
exec 2> >(tee  "${LOGDIR}/${TAG}.err" >&2)

# ---- Provenance Banner ----
echo "========== SLURM JOB INFO =========="
echo "Job ID            : ${JOB_ID}"
echo "Array Task ID     : ${TASK_ID}"
echo "Hostname          : $(hostname)"
echo "Date              : $(date)"
echo ""
echo "========== PHYSICAL PARAMETERS ======"
echo "Qubits (k)        : ${k}"
echo "V0                : ${V0} 2pi * MHz"
echo "Omega_max         : ${OM} 2pi * MHz"
echo "Detuning ±        : ${DELTA} 2pi * MHz"
echo "Total ramp time   : ${Ttot} µs"
echo "T_ramp_up/down    : ${Tup} µs"
echo "T_sweep           : ${Ts} µs"
echo "T2 (effective)    : ${T2} µs"
echo "====================================="
echo ""

# ---- Run Simulation ----
python rydberg_fidelity.py \
  --k "${k}" \
  --V0          "$V0" \
  --Omega_max   "$OM" \
  --Delta_start "-$DELTA" \
  --Delta_end   "$DELTA" \
  --T_ramp_up   "$Tup" \
  --T_sweep     "$Ts" \
  --T_ramp_down "$Tdown" \
  --T2          "$T2" \
  --num_steps   1000 \
  --outdir      "fidelity_${JOB_ID}"
