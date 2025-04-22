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
purification/
├── README.md                     # Project documentation
├── .env                          # Local IBM token (not committed)
├── .gitignore                   # Ignore cache, logs, env files, etc.
│ 
├── reqs/
│   └── environment.yml          # Conda environment definition
│ 
├── simulate.slurm               # SLURM job script to launch all QPA batch jobs
├── submit_all.sh                # Helper script to submit all simulations
├── clean.py                     # Aggregates and postprocesses simulation outputs
│ 
├── simulation_scripts/          # AER-based simulator (statevector/density)
│   ├── aer_simulation.py        # Main simulation script
│   ├── aer_simulation_extloop.py# Version with external control loop
│   └── aer_simulation.ipynb     # Playground notebook
│ 
├── estimate.slurm               # SLURM script for epsilon-sweep estimation jobs
├── combine_data.py              # Aggregates and postprocesses estimation outputs
│ 
├── estimation_scripts/          # Runtime Estimator (V2) simulations
│   ├── aer_estimation.py        # Main estimation script
│   ├── estimator_aer.ipynb      # Playground notebook
│   └── estimator_aer_notranspile.ipynb # External loop, no transpilation
│ 
├── sampler_scripts/             # Runtime Sampler-based simulations
│   ├── sampler_aer.ipynb        # Sampler (AER) with external loop
│   └── sampler_ibm.ipynb        # Sampler (IBM Quantum backend) notebook
│ 
├── full_dm_simulation/          # Optional: full density matrix simulations
├── env_tests/                   # Notebooks for testing environment and tools
├── QCT codes/                   # Related code on quantum character transformation
│
├── logs/                        # SLURM stdout/stderr outputs
├── data/                        # Final simulation results (.csv)
└── shared_data/                 # Shared intermediate results (e.g., cached outputs)
```

