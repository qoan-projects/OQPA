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
├── README.md                    # Project documentation
├── .env                         # Local IBM token (not committed)
├── .gitignore                   # Ignore cache, logs, env files, etc.
│ 
├── reqs/
│   └── environment.yml          # Conda environment definition
│ 
├── clean.py                     # Aggregates and postprocesses simulation outputs
├── combine_data.py              # Aggregates estimation outputs
│
├── aer_global_simulation_scripts/  # AER-based simulator scripts for global noise model + QPA
│   └── aer_simulation.py        # Main simulation script for QPA with global noise model
│
├── aer_trotter_estimation_scripts/ # Digital state preparation + QPA experiment
│   └── aer_estimation.py        # Main estimation script for Trotterized evolution
│ 
├── aer_ryd_estimation_scripts/  # Rydberg state preparation + QPA experiment
│   ├── ryd_sim_scripts/         # Rydberg simulation scripts
│   │    ├── run_ryd_sim.slurm   # Submit batch job for Rydberg simulations
│   │    └── ryd_sim.py          # Rydberg simulation implementation
│   └── custom_state_estimation.py # QPA estimation on extracted Rydberg eigenstates
│
├── full_dm_simulation/          # Full density matrix simulation implementation
│   └── circuit_based_full_dm.ipynb  # Jupyter notebook for full density matrix circuit simulation
│
├── ibm_global_sampler_scripts/  # IBM Quantum experiments with global noise model
│   └── three_circuits_ibm_global_sampler.py  # Implementation of QPA with three circuits on IBMQ
│
├── batching_engaging/           # Batching scripts for engagement cluster (e.g., SubMIT)
│   ├── estimate.sh             # Shell script for aer_estimation jobs
│   ├── estimate.slurm          # SLURM script for aer_estimation jobs
│   └── other SLURM and shell scripts for various experiments
│ 
├── batching_submit/             # Batching scripts for submission cluster (e.g., HPC)
│   ├── estimate.sh             # Shell script for estimation jobs
│   ├── estimate.slurm          # SLURM script for estimation jobs
│   └── other SLURM and shell scripts for HPC submission
│ 
├── data/                        # Intermediate simulation results
├── logs/                        # SLURM stdout/stderr outputs
├── shared_data/                 # Final results and processed data
│   ├── aer_global_simulation/   # Results from global noise model simulations
│   ├── aer_trotter_estimation/  # Results from Trotterized evolution experiments
│   ├── aer_ryd_estimation/      # Results from Rydberg state experiments
│   ├── three_circuits_ibm_global_sampler/      # Results from IBM Quantum experiments
│   ├── unitary_evolved_full_dm/ # Results from full density matrix simulations
│   ├── main_plotting.ipynb       # Notebook used to generate the main figures
│   └── SI_plotting.ipynb        # Notebook used to generate the supplementary figures
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


---

## Test Twirling

- **Location:** `test_twirling/` — contains scripts and helpers for randomized twirling tests used to validate measurement and noise-averaging routines.
- **Quick run:** from the project root you can run example scripts, e.g.: `python test_twirling/external_loop.py` (adjust arguments as needed for your setup).
- **Purpose:** these tests exercise twirling protocols and help verify that estimators and batching logic behave under randomized noise samples.