# Cyclic Hybrid QPA Strategy Simulation

This directory contains the implementation and simulation engine for the **Cyclic Hybrid Strategy** for Quantum Phase Estimation / State Purification (QPA). 

The code simulates a quantum circuit that utilizes $N$ quantum registers (where $N = 2i + 1$) to perform recursive purification steps involving parallel Schur tests (swap tests) and cyclic rotations. The goal is to evaluate the fidelity of this strategy under global depolarizing noise and analyze its error scaling properties (specifically looking for $\propto 1/N$ scaling).

## File Structure

- **`qpa_engine.py`**: The main simulation engine.
    - Defines the `HybridNRegStrategy` class which constructs the quantum circuit using Qiskit.
    - Implements the recursive logic: Parallel Schur Tests $\rightarrow$ Branching Logic $\rightarrow$ Cyclic Rotation $\rightarrow$ Recursion.
    - Runs simulations across a sweep of noise parameters ($\lambda$) using parallel processing (`ProcessPoolExecutor`).
    - Saves raw fidelity data to CSV files.

- **`analyze_results.py`**: Analysis and plotting script.
    - Aggregates results from individual simulation runs (different $N$).
    - Generates plots for:
        1. **Fidelity vs. Noise ($\lambda$)**: Comparing performance across different $N$.
        2. **Error Scaling**: Log-log plot of Logical Error ($1-F$) vs. Register Count ($N$).

- **`submit_job.sh`**: SLURM batch script.
    - configured to run the simulation on a high-performance cluster.
    - Uses SLURM Job Arrays to run simulations for multiple $N$ values (3, 5, 7, 9, etc.) concurrently.

## How to Use

### 1. Running Simulations Locally

You can run the simulation for a specific number of registers directly using Python:

```bash
# Example: Run for N=5 registers, k=1 copies, with 40 parallel workers
python qpa_engine.py --n 5 --k 1 --trials 4 --shots 10000 --workers 40
```

**Arguments:**
- `--n`: Number of registers (Must be odd: 3, 5, 7, ...). **Required**.
- `--k`: Number of qubits per register (default: 2).
- `--trials`: Depth of the recursive protocol (default: 3).
- `--shots`: Number of shots per simulation point (default: 10000).
- `--points`: Number of noise values ($\lambda$) to sweep (default: 20).
- `--workers`: Number of CPU cores to use for parallel processing.

### 2. Running on a Cluster (SLURM)

To run the full scaling analysis on a cluster:

```bash
sbatch submit_job.sh
```
*Note: You may need to adjust the `#SBATCH` parameters and the `NS` / `NWORKERS` arrays in the script to match your cluster's configuration and desired experiment range.*

### 3. Analyzing Results

After the simulations complete, result CSV files will be saved in `results_hybrid_scaling/`. To generate plots:

```bash
python analyze_results.py
```

This will produce:
- `hybrid_combined_*.csv`: Aggregated data file.
- `plot_fidelity_vs_lambda.png`: Visual comparison of fidelities.
- `plot_scaling_vs_n.png`: Scaling analysis graph.

## Strategy Overview

The **Hybrid N-Register Strategy** works by:
1.  **Parallel Testing**: Comparing pairs of registers using Schur tests.
2.  **Filtering**: Discarding pairs that fail the test.
3.  **Cyclic Rotation**: Permuting the survivors and a "reserve" register to mix pure states back into the pool.
4.  **Recursion**: Repeating the process to progressively purify the state.

### Algorithm Description

Here is the detailed algorithmic flow for the Cyclic Hybrid Strategy:

**Algorithm: Cyclic Hybrid Strategy (N-Register)**

**Registers**: $N$ quantum data registers $R_1, \dots, R_N$ (where $N=2m+1$ is odd); Ancilla qubits for parallel SWAP tests.  
**Input**: $N$ noisy copies of state $\rho$, max depth $T$.  
**Output**: A processed qudit in the reserve register.

1. **Initialize**: Define $m$ pairs $P_1=(R_1, R_2), \dots, P_m=(R_{N-2}, R_{N-1})$ and Reserve $R_{res} = R_N$.
2. **For** $t = 1$ to $T$ **do**:
3. &nbsp;&nbsp;&nbsp;&nbsp;**Parallel Test**: Perform SWAP test on each pair $P_i$. Obtain outcome vector $\vec{z} = [z_1, \dots, z_m]$.
4. &nbsp;&nbsp;&nbsp;&nbsp;**Filter**: Identify surviving pairs $S = \{ P_i \mid z_i = 0 \}$ (where test passed). Let $k = |S|$.
5. &nbsp;&nbsp;&nbsp;&nbsp;**If** $k > 1$ (Multiple survivors) **then**:
6. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Construct list $L$ containing all registers from pairs in $S$, followed by $R_{res}$.
7. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Cyclic Rotate**: Shift the last element ($R_{res}$) to the front of $L$.
8. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Re-assign pairs and reserve from $L$ for the next iteration.
9. &nbsp;&nbsp;&nbsp;&nbsp;**Else If** $k = 1$ (Single survivor pair $P_{surv} = (R_A, R_B)$) **then**:
10. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Execute **Linear Fallback** (N=3) using $R_A, R_B$ and $R_{res}$.
11. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Break** loop (or continue linear logic).
12. &nbsp;&nbsp;&nbsp;&nbsp;**Else** ($k=0$):
13. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;All pairs failed. Protocol terminates (failure branch).
14. **End For**
15. **Return** $R_{res}$.
