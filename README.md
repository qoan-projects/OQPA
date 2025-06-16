# QPA-Experiments: Quantum Purity Amplification

**QPA-Experiments** is a simulation framework for studying Quantum Purity Amplification (QPA), a protocol that amplifies the purity of noisy quantum states through iterative entanglement, measurement, and conditional operations. This project enables benchmarking QPA performance across a wide range of noise models and protocol parameters, with support for Trotterized Ising evolution and the SWAPNET architecture. Simulations are optimized for near-term quantum hardware and hybrid analog-digital platforms.

---

## 🛠️ Conda Environment Setup

You can set up your environment directly using the `environment.yml` file provided in the repository:

```bash
conda env create -f environment.yml
conda activate qpa_env
```

### Jupyter Notebook Support
If you're working with Jupyter notebooks:

```bash
conda install jupyter notebook
```

To use the QPA environment as a Jupyter kernel:
```bash
python -m ipykernel install --user --name=qpa_env --display-name "QPA Env"
jupyter notebook
```

---

## 🔐 IBM Quantum Token Setup

If you're using IBM Quantum services, create a `.env` file in the project root with:
```env
IBM_QUANTUM_TOKEN=your_ibmq_token_here
```

---

## ⚡ GPU-Accelerated Qiskit Aer on SubMIT

Install the GPU-enabled Qiskit Aer backend:
```bash
pip install qiskit-aer-cu11
```

Then request a GPU node:
```bash
salloc --partition=submit-gpu-a30 --cpus-per-gpu=1 --gres=gpu:1 --mem=8G --time=01:00:00
```

Set up CUDA manually on the node:
```bash
export CUDA_ROOT=/usr/local/cuda
export PATH=$CUDA_ROOT/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_ROOT/lib64:$LD_LIBRARY_PATH
```

Check it works:
```bash
nvcc --version
python -c "from qiskit_aer import AerSimulator; print(AerSimulator().available_devices())"
```
Expected output:
```
('CPU', 'GPU')
```

---

## 🧪 Running Batch Simulations

To launch a full batch of QPA simulations across different numbers of QPA rounds (`nqpa`) and Trotter steps (`ntrot`), simply run the script below. You can modify the parameters (such as `nqpa`, `ntrot`, `k`, `shots`, and epsilon sweep settings) directly in the `submit_all.sh` file:

```bash
bash submit_all.sh
```

This script submits SLURM job arrays that sweep over different values of depolarizing noise strength (`ε`). Each job in the array corresponds to a different `ε` value.

### 🔍 Where to find outputs and logs
- **Simulation output CSVs** are saved in:
  ```
  "data/estimation_<JOBID>_k<K>_shots<SHOTS>_eps<MIN>-<MAX>_s<STEPS>/"
  ```
- **Log files** are saved in:
  ```
  "logs/estimation_<JOBID>_k<K>_shots<SHOTS>_eps<MIN>-<MAX>_s<STEPS>/"
  ```
  Each file is named by QPA round, Trotter step count, and epsilon index. For example:
  ```
  "nqpa2_ntrot5_eps17.csv"
  "nqpa2_ntrot5_eps17.out"
  "nqpa2_ntrot5_eps17.err"
  ```

These directories are automatically created for each batch job submission.

---

## 📁 Project Directory Overview

```bash
OQPA/
├── README.md                     # Project documentation
├── .env                          # Local IBM token (not committed)
├── .gitignore                   # Ignore cache, logs, env files, etc.
│ 
├── reqs/
│   └── environment.yml          # Conda environment definition
│ 
├── clean.py                     # Aggregates and postprocesses simulation outputs
├── combine_data.py              # Aggregates estimation outputs
├── estimation_scripts/          # Runtime Estimator (V2) simulations
│   ├── aer_estimation.py        # Main estimation script
│   ├── custom_state_estimation.py # Custom state estimation implementation
│   ├── no_if_else_estimation.py  # Estimation without conditional logic
│   └── other estimation scripts
│ 
├── ibm_backends_scripts/        # IBM Quantum backend scripts
│   ├── estimator_fakebackend_and_ibm.ipynb # Notebook for fake backend and IBM estimation
│   ├── fakebackend_estimation.py # Estimation using fake backend
│   ├── fakebackend_no_if_else_estimation.py # No-if-else estimation with fake backend
│   ├── ibmprocessors_estimation.py # Estimation using IBM quantum processors
│   └── ladder_step_initialization_estimation.py # Estimation with ladder step initialization
│ 
├── simulation_scripts/          # AER-based simulator scripts
│   ├── aer_simulation.py        # Main simulation script
│   └── other simulation scripts
│ 
├── ryd_sim_scripts/            # Rydberg simulation scripts
│   ├── run_ryd_sim.slurm       # Submit batch job for Rydberg simulations
│   └── ryd_sim.py              # Rydberg simulation file
│ 
├── batching_engaging/           # Batching scripts for engagement cluster (e.g., SubMIT)
│   ├── estimate.sh             # Shell script for aer_estimation jobs
│   ├── estimate.slurm          # SLURM script for aer_estimation jobs
│   ├── fake_backend_engaging.sh # Shell script for fake backend jobs
│   ├── fake_backend_engaging.slurm # SLURM script for fake backend jobs
│   ├── ladder_step_engaging.sh # Shell script for ladder step initialization jobs
│   ├── ladder_step_engaging.slurm # SLURM script for ladder step initialization jobs
│   ├── new_fake_backend_engaging.sh # Updated fake backend engagement script
│   ├── new_fake_backend_engaging.slurm # Updated SLURM script for fake backend
│   ├── no_if_else_fidelity_comparison.sh # Shell script for no-if-else fidelity comparison
│   └── no_if_else_fidelity_comparison.slurm # SLURM script for fidelity comparison
│ 
├── batching_submit/             # Batching scripts for submission cluster (e.g., HPC)
│   ├── estimate.sh             # Shell script for estimation jobs
│   ├── estimate.slurm          # SLURM script for estimation jobs
│   ├── fake_backend_submit.sh  # Shell script for fake backend jobs
│   ├── fake_backend_submit.slurm # SLURM script for fake backend jobs
│   ├── ibmprocessors_submit.sh # Shell script for IBM processors jobs
│   ├── ibmprocessors_submit.slurm # SLURM script for IBM processors jobs
│   ├── ryd_submit.sh           # Shell script for Rydberg simulation jobs
│   ├── ryd_submit.slurm        # SLURM script for Rydberg simulation jobs
│   └── simulate.slurm          # Main simulation SLURM script
│ 
├── test_single_ryd_batch/       # Test scripts for single Rydberg batch
│ 
├── data/                        # Intermediate simulation results
├── logs/                        # SLURM stdout/stderr outputs
├── shared_data/                 # Final results and processed data
├── writeup/                     # Documentation and summaries
└── QCT_codes/                   # Quantum Character Transformation related code
```

## 🔄 Batching System Overview

The batching system is designed to handle distributed computing across different computational clusters. It consists of two main components:

### Batching Engaging (`batching_engaging/`)
This directory contains SLURM scripts and shell scripts designed for the engagement cluster (typically SubMIT). These scripts are optimized for:
- Shorter runtime jobs
- Quick turnaround for iterative development
- Testing new features and algorithms
- Fidelity comparisons and small-scale simulations

### Batching Submit (`batching_submit/`)
This directory contains scripts designed for large-scale HPC cluster submissions. These scripts are optimized for:
- Large-scale batch simulations
- Long-running jobs
- Production runs with many parameter sweeps
- Resource-intensive computations

Each type of simulation (fake backend, Rydberg, ladder step initialization) has corresponding scripts in both directories to handle different computational requirements and cluster configurations.

