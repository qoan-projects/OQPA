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
│   ├── circuit_builder.py      # Factory for creating circuits (Dynamic vs Unrolled)
│   ├── hybrid_topology.py      # Logic for unrolling the QPA decision tree
│   └── noise_models.py         # Noise injection strategies (Depolarizing vs Twirling)
├── execution/
│   ├── backend_handler.py      # Wrappers for AER, Fake, and IBM Runtime backends
│   └── job_manager.py          # Handles job submission and tracking
├── analysis/
│   ├── post_selection.py       # Filtering logic for unrolled circuits
│   ├── fidelity_calc.py        # Fidelity computation
│   └── result_processor.py     # Orchestrates analysis
├── legacy/                     # Original codebase (reference)
├── main.py                     # CLI Entry Point
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (IBM Token, CRN)
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
python main.py --backend aer --n 5 --k 2 --trials 3 --shots 1000 --output results_aer.csv
```

### 2. Run on Fake Backend (Unrolled Simulation)
Simulates hardware constraints (no dynamic control) using unrolled circuits and Pauli Twirling noise.
```bash
python main.py --backend fake --device ibm_brisbane --n 5 --k 2 --trials 3 --shots 1000 --n-random 10 --output results_fake.csv
```

### 3. Run on Real Hardware
Submits jobs to IBM Quantum.
```bash
python main.py --backend ibm --device ibm_brisbane --n 5 --k 2 --trials 3 --shots 4000 --n-random 20 --output results_ibm.csv
```

### SLURM (Batch Execution)
For large-scale simulations on a cluster, use the provided SLURM script:
```bash
sbatch ibm_global_sampler.slurm
```
Ensure you update the parameters in the SLURM script (e.g., partition, environment name) before running.

## Methodology
- **Dynamic Method**: Uses a single circuit with `if_test` instructions to implement the probabilistic success/failure logic of QPA.
- **Unrolled Method**: Pre-calculates all possible execution paths (success/failure branches) and generates a set of static circuits. During analysis, shots are filtered based on ancilla measurements to mimic the conditional logic.
- **Pauli Twirling**: For hardware/fake execution, coherent noise is converted into stochastic Pauli noise by averaging over multiple circuit instances with random Pauli gates inserted.
