from qiskit import QuantumCircuit, transpile, ClassicalRegister, QuantumRegister
from qiskit_aer import AerSimulator

def debug_heuristic_execution():
    print("\n=== DEBUGGING HEURISTIC LOGIC FLOW ===")
    
    # 1. Setup Resources
    # We use 1 qubit per register (k=1) for simplicity in reading bitstrings
    k = 1
    qr_data = [QuantumRegister(k, f"R{i+1}") for i in range(5)]
    qr_ctrl = QuantumRegister(4, "ctrl")
    
    # Classical Registers to capture the DECISION logic
    cr_par = ClassicalRegister(2, "par")
    cr_cross = ClassicalRegister(1, "cross")
    cr_verify = ClassicalRegister(1, "verify")
    
    # Classical Register to capture the RESULTING STATE of R1-R5
    cr_state = ClassicalRegister(5, "final_state")
    
    qc = QuantumCircuit(*qr_data, qr_ctrl, cr_par, cr_cross, cr_verify, cr_state)
    
    # 2. Initialize the Problematic State: |00110>
    # R1, R2, R5 = 0. R3, R4 = 1.
    qc.x(qr_data[2]) # R3
    qc.x(qr_data[3]) # R4
    
    # 3. Define Helper for Schur Test (Same as your class)
    def schur_test(ctrl_idx, res_bit, rA, rB):
        qc.reset(qr_ctrl[ctrl_idx])
        qc.h(qr_ctrl[ctrl_idx])
        qc.cswap(qr_ctrl[ctrl_idx], rA[0], rB[0])
        qc.h(qr_ctrl[ctrl_idx])
        qc.measure(qr_ctrl[ctrl_idx], res_bit)

    # 4. EXECUTE ONE LAYER OF HEURISTIC LOGIC (Manual Unroll)
    # We want to see exactly what decisions it makes.
    
    # --- Parallel Tests ---
    schur_test(0, cr_par[0], qr_data[0], qr_data[1]) # R1 vs R2 (Exp: 0)
    schur_test(1, cr_par[1], qr_data[2], qr_data[3]) # R3 vs R4 (Exp: 0, because 11 is symmetric)
    
    # --- Path A Logic (Both Pass) ---
    with qc.if_test((cr_par, 0)): 
        # Cross Test: R1(0) vs R3(1) (Exp: 50% 0, 50% 1)
        schur_test(2, cr_cross[0], qr_data[0], qr_data[2])
        
        # A1: Cross Pass (False Positive)
        with qc.if_test((cr_cross, 0)):
             # Verify: R2(0) vs R4(1)
            schur_test(3, cr_verify[0], qr_data[1], qr_data[3])
            
            # A11: Verify Pass (Double False Positive) -> Cyclic Rotate
            with qc.if_test((cr_verify, 0)):
                # Perform Rotation and STOP to inspect
                for i in range(k):
                    for j in range(4, 0, -1):
                        qc.swap(qr_data[j][i], qr_data[j-1][i])
            
            # A12: Verify Fail
            with qc.if_test((cr_verify, 1)):
                pass # Return R5 (Do nothing to state)

        # A2: Cross Fail (Detection)
        with qc.if_test((cr_cross, 1)):
            # Verify: R2(0) vs R5(0) -> Should Pass
            schur_test(3, cr_verify[0], qr_data[1], qr_data[4])
            
            # A21: Pass -> Rotate specific subset (simulated swap for visual check)
            with qc.if_test((cr_verify, 0)):
                 # Swap R1, R2, R5 to front? 
                 # Let's just NOT touch them so we see the clean state 00110
                 pass

    # 5. Measure Final State of Data Qubits
    # Order in bitstring will be R5 R4 R3 R2 R1 (Qiskit standard)
    for i in range(5):
        qc.measure(qr_data[i], cr_state[i])

    # 6. Run Simulation
    sim = AerSimulator()
    qc = transpile(qc, sim)
    result = sim.run(qc, shots=1000).result()
    counts = result.get_counts()
    
    print(f"{'PAR':<5} | {'CROSS':<5} | {'VER':<5} | {'R5 R4 R3 R2 R1':<15} | {'PROB':<5}")
    print("-" * 50)
    
    for key, count in counts.items():
        # Key format: "final_state verify cross par" (Space separated)
        # Note: Qiskit reverses register order in the key string.
        # Check your specific Qiskit version output, usually: "State Ver Cross Par"
        parts = key.split()
        
        # Parse based on register definitions:
        # cr_state (5 bits), cr_verify (1), cr_cross (1), cr_par (2)
        state_bits = parts[0]
        ver_bit = parts[1]
        cross_bit = parts[2]
        par_bits = parts[3]
        
        prob = count / 1000.0
        print(f"{par_bits:<5} | {cross_bit:<5} | {ver_bit:<5} | {state_bits:<15} | {prob:.3f}")

if __name__ == "__main__":
    debug_heuristic_execution()