
import sys
import random
from qiskit import transpile
from qiskit_aer import AerSimulator
from core.strategies.unrolled import UnrolledStrategy
from core.noise_models import StandardDepolarizingStrategy

def simulate_unrolled_path():
    print("--- Debugging Unrolled Logic ---")
    
    # Parameters
    n = 5
    k = 2
    trials = 3
    epsilon = 0.0 # No noise first to check logic
    
    strategy = UnrolledStrategy(n_registers=n, k=k, n_trials=trials)
    
    # Build circuits (epsilon=0)
    circuits_data = strategy.build(epsilon)
    print(f"Generated {len(circuits_data)} unrolled circuits/paths.")
    
    # We want to check if the circuits correctly implement the QPA logic.
    # Specifically, if a path assumes "success" (measurement 0), does it actually output the correct state?
    
    # Let's pick the "All Success" path (usually the first one if product iterates 0,1)
    # The first path corresponds to outcomes (0,0), (0,0), ...
    
    path_0 = circuits_data[0]
    print(f"Checking Path 0: Conditions {path_0['conditions']}")
    
    qc = path_0['circuit']
    
    # Run on Aer
    sim = AerSimulator()
    qc_transpiled = transpile(qc, sim)
    result = sim.run(qc_transpiled, shots=1000).result()
    counts = result.get_counts()
    
    print(f"Path 0 Counts (No Noise): {counts}")
    
    # In ideal case (no noise), we start with |0...0> state (default init).
    # QPA purifies inputs. If inputs are |0>, output should be |0>.
    # So we expect readout '00'.
    
    # What if we inject noise?
    # If we inject X errors on some registers, does the circuit detect it?
    # Unrolled circuits are static. They don't react.
    # They are valid ONLY if the measurement outcomes MATCH the conditions.
    
    # So to verify, we must check if the ANCILLA measurements match the path conditions.
    # The 'counts' dictionary keys contain both readout and ancilla measurements.
    # Qiskit result keys are "clbit_N ... clbit_0".
    
    # We need to map classical bits to the conditions.
    # In UnrolledStrategy, we use 'anc_meas' register for history.
    # Let's see the clbits in the circuit.
    
    print("Circuit Clbits:", qc.clbits)
    
    # The 'conditions' dict maps {cl_idx: expected_val}.
    # We need to check if the simulation output respects this.
    # But wait, we forced the path construction assuming these outcomes.
    # We didn't force the outcomes in the simulation.
    # In a simulation, the ancilla measurements will be probabilistic based on the state.
    # If we provide input |0...0> (perfect state), the Schur tests should always yield 0 (success).
    # So for epsilon=0, the "All Success" path should be the ONLY one with non-zero probability?
    # And "Failure" paths should have 0 probability?
    
    # Let's verify this hypothesis.
    
    # We need to parse the counts to separate readout and ancilla measurements.
    # cr_readout is usually the first or last register added?
    # In QPARegisters:
    # regs = [*qr_data, *qr_ancilla, cr_readout, cr_ancilla]
    # So cr_readout is before cr_ancilla?
    # Wait, get_circuit_registers order matters.
    # regs.extend(self.qr_ancilla) -> regs.append(self.cr_readout) -> regs.append(self.cr_ancilla)
    # So order is: [Data, Ancillas, Readout, AncillaMeas]
    # Qiskit prints counts as "AncillaMeas Readout" (reversed order usually? or depends on bit significance)
    # Actually Qiskit prints from most significant register to least?
    # Usually: "reg_N ... reg_0" where reg_N is the last added?
    
    # Let's inspect the counts keys length.
    total_clbits = qc.num_clbits
    print(f"Total Clbits: {total_clbits}")
    
    # Run simulation for ALL paths and check which one occurs
    print("\nSimulating all paths (Epsilon=0)...")
    hits = 0
    for i, item in enumerate(circuits_data):
        qc_i = item['circuit']
        conds = item['conditions']
        
        qc_t = transpile(qc_i, sim)
        res = sim.run(qc_t, shots=100).result()
        cnts = res.get_counts()
        
        # Check if we got any results compatible with the conditions
        # Actually, for a static circuit, the ancilla measurements are PART of the circuit.
        # If we run path_i, we get some measurements.
        # Ideally, if input is perfect |0>, we should only see 0 measurements on ancillas.
        # If path_i assumes a '1' measurement (failure), but the physics says '0' (success),
        # then this path is physically impossible (probability 0) for this input.
        # But since we force the circuit structure (swaps etc) based on the assumption,
        # the measurement result tells us if the assumption held.
        
        # If we run path_i (assumes failure), and we measure 0 (success),
        # then this run is INVALID for this path.
        # This is exactly what post-selection is.
        
        # So for epsilon=0 (perfect input), only the "All Success" path should yield valid runs.
        # Valid run = measurements match conditions.
        
        # Let's verify if the conditions align with the measurements.
        
        # We need to know which bit index corresponds to which condition.
        # conditions is {cl_idx: val}
        # cl_idx is the index in the global list of clbits.
        
        total_shots = 0
        valid_shots = 0
        
        for key in cnts:
            # key is a bitstring. We need to map it to indices.
            # Qiskit bitstring is reversed: bit[N-1] ... bit[0]
            # remove spaces
            full_bin = key.replace(" ", "")
            # Reverse to get bit[0] ... bit[N-1]
            full_bin_ordered = full_bin[::-1]
            
            is_valid = True
            for cl_idx, val in conds.items():
                if int(full_bin_ordered[cl_idx]) != val:
                    is_valid = False
                    break
            
            if is_valid:
                valid_shots += cnts[key]
            
            total_shots += cnts[key]
            
        if valid_shots > 0:
            print(f"Path {i} (Conds: {conds}): Valid Shots = {valid_shots}/{total_shots}")
            hits += 1
            
    print(f"Paths with valid runs: {hits}")
    if hits == 1:
        print("PASS: Only one path (All Success) is valid for noiseless input.")
    else:
        print(f"FAIL: {hits} paths are valid (Expected 1).")

if __name__ == "__main__":
    simulate_unrolled_path()
