# Development Roadmap

This roadmap outlines the steps to transition from the legacy codebase to the modular architecture.

## Phase 1: Core Logic Refinement
**Goal**: Establish the circuit generation and noise injection foundation.

- [x] **Refactor `core/hybrid_topology.py`**:
    - [x] Ensure `UnrolledHybridStrategy` fully implements the recursive logic.
    - [x] Add support for injecting a `NoiseStrategy` callback during circuit generation.
    - [x] Verify that `conditions` (ancilla expectations) are correctly recorded for every path.
- [x] **Implement `core/circuit_builder.py`**:
    - [x] Create abstract `CircuitBuilder`.
    - [x] Implement `DynamicCircuitBuilder` (port logic from `legacy/cyclid_method/qpa_engine.py`).
    - [x] Implement `UnrolledCircuitBuilder` (wrapper around `hybrid_topology`).
- [x] **Implement `core/noise_models.py`**:
    - [x] Create `PauliTwirlingStrategy` class.
    - [x] Create `StandardDepolarizingStrategy` class.
    - [x] Ensure they share a common interface.

## Phase 2: Execution Engine
**Goal**: robust job submission for local and remote backends.

- [x] **Create `execution/backend_handler.py`**:
    - [x] Factory to get `AerSimulator`, `FakeBackend`, or `QiskitRuntimeService`.
- [x] **Create `execution/job_manager.py`**:
    - [x] Implement `submit_batch(circuits, backend)`.
    - [x] Handle splitting large batches (if necessary) for IBM backends.
    - [x] Implement job ID tracking (save to JSON/CSV) to allow retrieving results later.

## Phase 3: Analysis Pipeline
**Goal**: Turn raw counts into fidelity numbers.

- [x] **Implement `analysis/post_selection.py`**:
    - [x] Function to filter counts based on a `conditions` dictionary.
    - [x] Logic to aggregate results from multiple "path" circuits.
- [x] **Implement `analysis/fidelity_calc.py`**:
    - [x] Calculate fidelity from aggregated counts.
    - [x] Standardize output format (CSV).

## Phase 4: Integration
**Goal**: End-to-end execution.

- [x] **Create `main.py`**:
    - [x] CLI using `argparse`.
    - [x] Orchestrate the full pipeline: Builder -> Noise -> Runner -> Analyzer.
- [x] **Verification**:
    - [x] Run `main.py --backend aer` and compare results with `legacy/cyclid_method`.
    - [x] Run `main.py --backend fake` and verify it runs without errors.

## Phase 5: Documentation & Polish
- [ ] Add docstrings to all classes.
- [ ] Create a tutorial notebook.
