# QPA Cyclic Project - Modular Architecture

## Overview
This project implements the Quantum Purification Algorithm (QPA) using a cyclic method. It provides a modular framework for simulations on:
- **Qiskit AER Simulators**: Using dynamic circuits (`if_test`) and ideal noise models.
- **IBM Fake Backends**: Using static unrolled circuits and Pauli twirling.
- **IBM Real Hardware**: Using static unrolled circuits and Pauli twirling.

## Directory Structure
```
cyclic_project/
├── core/
│   ├── strategies/             # Circuit generation strategies
│   │   ├── base.py             # Base strategy class
│   │   ├── dynamic.py          # Dynamic circuit strategy (if_test)
│   │   └── unrolled.py         # Unrolled circuit strategy (static paths)
│   ├── circuit_factory.py      # Factory for creating strategies
│   ├── registers.py            # Quantum/Classical register management
│   ├── noise_models.py         # Noise injection strategies (Depolarizing vs Twirling)
│   ├── ops.py                  # Quantum operations (gates, measurements)
│   └── hybrid_topology.py      # Topology mapping helpers
├── execution/
│   ├── runner.py               # Main execution engine
│   ├── job_service.py          # Job submission and tracking service
│   ├── backend_handler.py      # Wrappers for AER, Fake, and IBM Runtime backends
│   └── transpiler_service.py   # Transpilation logic
├── analysis/
│   ├── result_processor.py     # Results extraction and aggregation
│   ├── fidelity_calc.py        # Fidelity computation logic
│   └── post_selection.py       # Filtering logic for unrolled circuits
├── data/
│   ├── jobs/                   # Job history and results storage
│   ├── logs/                   # Execution logs
│   └── results/                # Aggregated CSV results
├── scripts/
│   ├── batch_job.slurm         # SLURM submission script with examples
│   └── plot_results.py         # Plotting tool
├── utils/
│   ├── config.py               # Configuration management
│   └── paths.py                # Path management
├── main.py                     # CLI Entry Point
├── retrieve_results.py         # Job retrieval and processing tool
└── requirements.txt            # Python dependencies
```

## Data Organization
Jobs are organized hierarchically to facilitate efficient retrieval and management.

**Standard Runs:**
```
data/jobs/<backend>/<device>/n<N>_k<K>_t<Trials>/p<Points>/s<Shots>_c<Random>/<timestamp>/
```

**No-Reset Runs:**
```
data/jobs/<backend>/<device>/no_reset/n<N>_k<K>_t<Trials>/p<Points>/s<Shots>_c<Random>/<timestamp>/
```

## Installation

1.  **Environment Setup**:
    ```bash
    conda create -n qpa_env python=3.10
    conda activate qpa_env
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Create a `.env` file in the root directory (or rename `.env.example` if available) and add your IBM Quantum credentials:
    ```ini
    IBM_QUANTUM_TOKEN=your_token_here
    CRN=your_crn_here
    ```

## Usage

### 1. Run on AER (Dynamic Simulation)
Fast simulation using Qiskit Aer's dynamic circuit capabilities.
```bash
python main.py --backend aer --method dynamic --n 5 --k 2 --trials 3 --points 25 --shots 1000 --output results_aer.csv
```

### 2. Run on Fake Backend (Unrolled Simulation)
Simulates hardware constraints (no dynamic control) using unrolled circuits and Pauli Twirling noise.
```bash
python main.py --backend fake --device ibm_brisbane --n 5 --k 2 --trials 3 --points 25 --shots 1000 --n-random 10 --output results_fake.csv
```

### 3. Run with No-Reset (Experimental)
Run simulation without resetting ancilla qubits (uses fresh ancillas for each step). This mimics hardware where reset is costly or unavailable.
```bash
python main.py --backend aer --method unrolled --n 5 --k 2 --trials 3 --no-reset --output results_no_reset.csv
```

### 4. Run on Real Hardware (Submit Only)
Submits jobs to IBM Quantum in "Post-Only" mode (returns immediately).
```bash
python main.py --backend ibm --device ibm_brisbane --n 5 --k 2 --trials 3 --points 25 --shots 4000 --n-random 100 --batch-size 200 --post-only --output results_ibm_submit.csv
```

### 5. Retrieve Results
Retrieves results from IBM or previously saved local simulations.
```bash
# Standard retrieval
python retrieve_results.py --backend ibm --device ibm_brisbane --n 5 --k 2 --trials 3 --output results_ibm.csv

# Retrieve No-Reset jobs
python retrieve_results.py --backend aer --device aer_unrolled --n 5 --k 2 --trials 3 --no-reset --output results_no_reset.csv
```

### 6. Plot Results
Visualizes the fidelity decay curves with error bars and theoretical comparisons.
```bash
python scripts/plot_results.py results_ibm.csv results_no_reset.csv --output plot.png
```

## SLURM (Batch Execution)
For large-scale simulations on a cluster, use the provided SLURM script. It contains pre-configured examples for all workflows.

1.  **Edit the script**: Uncomment the desired example command and its corresponding `#SBATCH --job-name`.
2.  **Submit**:
    ```bash
    cd scripts
    sbatch batch_job.slurm
    ```
    This runs unbuffered (`python -u`) to ensure real-time logging in `data/logs/`.

## Methodology
- **Dynamic Method**: Uses a single circuit with `if_test` instructions to implement the probabilistic success/failure logic of QPA.
- **Unrolled Method**: Pre-calculates all possible execution paths (success/failure branches) and generates a set of static circuits. During analysis, shots are filtered based on ancilla measurements to mimic the conditional logic.
- **Parameterized Method**: Uses Qiskit's `Parameter` objects to create a single circuit template with placeholders for Pauli Twirling gates (`RX`, `RZ`). This significantly reduces transpilation time and memory usage by submitting a single circuit with multiple parameter bindings (PUBs).
- **Pauli Twirling**: For hardware/fake execution, coherent noise is converted into stochastic Pauli noise by averaging over multiple circuit instances with random Pauli gates inserted.
- **No-Reset Optimization**: Optionally disables qubit reset instructions, allocating new ancilla qubits for each trial step. This increases qubit count but avoids potential reset errors on hardware.
