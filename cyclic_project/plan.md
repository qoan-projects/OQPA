# Analysis of AER Dynamic Simulation Performance: Legacy vs. Modular

## 1. Issue Overview
The user reported a significant performance degradation when running `aer_dynamic` simulation with `n=7, k=2` using the new modular `main.py` compared to the legacy `qpa_engine.py`. The legacy code completed the entire curve quickly, while the new code only processed 3 points in 12 hours.

## 2. Architecture Comparison

### Legacy Code (`cyclid_method/qpa_engine.py`)
- **Parallelization Model**: Process-based parallelization using `concurrent.futures.ProcessPoolExecutor`.
- **Granularity**: Each `lambda` point is a separate, independent task.
- **Worker Logic (`simulate_point`)**:
    1.  Re-instantiates `HybridNRegStrategy` (lightweight).
    2.  Builds the circuit for that specific lambda.
    3.  **Transpiles** the circuit using `transpile(qc, AerSimulator(), optimization_level=1)`.
    4.  Runs simulation using `AerSampler()`.
- **Efficiency**: 
    - Full CPU utilization (multi-core) because each lambda runs in a separate process.
    - Low overhead: Circuits are built and transpiled only once per lambda point.
    - `optimization_level=1`: Faster transpilation.

### Modular Code (`main.py` + `execution/job_manager.py`)
- **Parallelization Model**: **Sequential** loop over `lambdas`.
    - `for epsilon in tqdm(lambdas): ...`
- **Granularity**: Inside the loop, it creates a batch of circuits (usually 1 for dynamic).
- **Bottleneck**:
    - **Transpilation**: `JobManager.submit_batch` calls `transpile` with `optimization_level=3` (default for non-sims, but code sets `opt_level=1` for AER/Fake). However, this happens *sequentially* for every lambda point.
    - **Single-Threaded Execution**: The main loop runs in a single process. While `AerSampler` might use threads internally for tensor network contraction, for `n=7` (14 qubits + ancillas), the circuit is small enough that overhead dominates, or it's not effectively parallelizing a single shot execution as well as running multiple independent simulations.
    - **Overhead**: The modular architecture adds layers of abstraction (Builder -> Manager -> Handler -> Backend) which might introduce slight overhead, but the **lack of process-level parallelism** is the primary culprit.

## 3. Why `n=7` is Slow
- `n=7, k=2` involves 14 data qubits + ~3 ancillas + dynamic control flow.
- Simulating dynamic circuits (`if_test`) on AER can be slower than static circuits if not optimized, but the legacy code proves it *can* be fast.
- The critical difference is that the legacy code runs `N_points` simulations **simultaneously** (e.g., 20 processes for 20 points), reducing wall-clock time by factor of `N_cpus`. The new code runs them one after another.

## 4. Upgrade Plan for `main.py`

To restore the performance of the legacy code while maintaining the modular architecture, we need to introduce parallel execution for the lambda sweep.

### Plan: Parallelize the Lambda Loop

1.  **Refactor `main.py`**:
    - Move the "Simulation Logic" (Build -> Transpile -> Run -> Process) for a single lambda point into a standalone function (e.g., `run_single_point`).
    - This function needs to accept all necessary config (args, builder class, noise class, etc.) and return the result for that point.

2.  **Use `ProcessPoolExecutor`**:
    - Instead of the `for epsilon in tqdm(lambdas):` loop, create a list of tasks.
    - Use `concurrent.futures.ProcessPoolExecutor` to map `run_single_point` over the `lambdas` array.
    - This allows running multiple lambda points concurrently, utilizing all available CPU cores on the SLURM node.

3.  **Handling `JobManager` in Parallel**:
    - `JobManager` and `BackendHandler` might not be picklable or thread-safe if they hold open connections or complex Qiskit objects.
    - **Solution**: Re-instantiate `JobManager` (or at least the `AerSampler`) inside the worker function, similar to how the legacy code re-instantiates `HybridNRegStrategy`. For AER, this is cheap.

4.  **Optimizing Transpilation**:
    - Ensure `optimization_level` is set to 1 for AER simulations in the worker to save transpilation time (already present in `JobManager` but good to verify).

5.  **Data Aggregation**:
    - The main process collects results from futures as they complete and saves them to the CSV.

### Impact on Other Backends
- **Fake Backend**: Also benefits significantly from this parallelization.
- **IBM Backend**: **Do NOT** parallelize with `ProcessPoolExecutor`. IBM Runtime has queue limits and rate limits. We should keep the sequential batch submission for IBM, or use `asyncio` for concurrent job submission if needed, but not CPU multiprocessing. We can add a check `if backend == 'aer' or backend == 'fake': use_parallel else: use_sequential`.

## 5. Summary
The "slowness" is simply serial vs. parallel execution. The legacy code was explicitly designed for high-throughput local simulation via multiprocessing. The new `main.py` was designed with a "submit batch to hardware" mindset which is inherently serial/async. We need to re-introduce the multiprocessing path for local simulators.
