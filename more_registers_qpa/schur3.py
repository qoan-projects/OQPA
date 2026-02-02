#!/usr/bin/env python3

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.quantum_info import Operator, Statevector
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram
import matplotlib.pyplot as plt

class SchurTransformN3:
    """
    Implements the Schur Transform for N=3 Qubits.
    This is the unitary that diagonalizes the permutation symmetry.
    
    Output Basis Mapping (|q2 q1 q0>):
    -----------------------------------
    q2=0: Symmetric Subspace (Spin-3/2)
        |000> -> |J=3/2, m=3/2>  ( |000> )
        |001> -> |J=3/2, m=1/2>  ( W-state type )
        |010> -> |J=3/2, m=-1/2> ( W-state type )
        |011> -> |J=3/2, m=-3/2> ( |111> )
    
    q2=1: Mixed Subspace (Spin-1/2)
        q1 encodes the Path (multiplicity).
        q0 encodes the Magnetic Number (data).
        
        |100> -> |J=1/2, m=1/2,  Path=0> (from Singlet 1-2)
        |101> -> |J=1/2, m=-1/2, Path=0>
        |110> -> |J=1/2, m=1/2,  Path=1> (from Triplet 1-2)
        |111> -> |J=1/2, m=-1/2, Path=1>
    """
    
    def __init__(self):
        self.matrix = self._build_cg_matrix()

    def _build_cg_matrix(self):
        # We construct the 8x8 unitary. Rows are Computational, Cols are Schur.
        # Wait, Qiskit Operator(matrix): matrix[i, j] is <i|U|j>.
        # We want to define the columns as the Schur Basis vectors expressed in Computational Basis.
        
        # Computational Basis Index Map
        # 0:000, 1:001, 2:010, 3:011, 4:100, 5:101, 6:110, 7:111
        
        # --- BLOCK 1: SYMMETRIC (J=3/2) ---
        # Maps to outputs |000>, |001>, |010>, |011>
        
        # |3/2, 3/2> = |000>
        v_s_32 = np.zeros(8); v_s_32[0] = 1.0
        
        # |3/2, 1/2> = 1/sqrt(3) (|001> + |010> + |100>)
        v_s_12 = np.zeros(8); v_s_12[[1, 2, 4]] = 1.0/np.sqrt(3)
        
        # |3/2, -1/2> = 1/sqrt(3) (|011> + |101> + |110>)
        v_s_m12 = np.zeros(8); v_s_m12[[3, 5, 6]] = 1.0/np.sqrt(3)
        
        # |3/2, -3/2> = |111>
        v_s_m32 = np.zeros(8); v_s_m32[7] = 1.0

        # --- BLOCK 2: MIXED (J=1/2) ---
        # Maps to outputs |100>, |101> (Path 0) and |110>, |111> (Path 1)
        
        # Path 0 (From Singlet 1-2): 1/sqrt(2) (|01> - |10>) x |state>
        
        # |1/2, 1/2, P0> = 1/sqrt(2) (|010> - |100>)
        v_m_p0_12 = np.zeros(8)
        v_m_p0_12[2] = 1.0/np.sqrt(2)
        v_m_p0_12[4] = -1.0/np.sqrt(2)
        
        # |1/2, -1/2, P0> = 1/sqrt(2) (|011> - |101>)
        v_m_p0_m12 = np.zeros(8)
        v_m_p0_m12[3] = 1.0/np.sqrt(2)
        v_m_p0_m12[5] = -1.0/np.sqrt(2)
        
        # Path 1 (From Triplet 1-2, orthogonal to Symmetric):
        # |1/2, 1/2, P1> = 1/sqrt(6) (2|001> - |010> - |100>)
        v_m_p1_12 = np.zeros(8)
        v_m_p1_12[1] = 2.0/np.sqrt(6)
        v_m_p1_12[2] = -1.0/np.sqrt(6)
        v_m_p1_12[4] = -1.0/np.sqrt(6)
        
        # |1/2, -1/2, P1> = 1/sqrt(6) (|011> + |101> - 2|110>)
        v_m_p1_m12 = np.zeros(8)
        v_m_p1_m12[3] = 1.0/np.sqrt(6)
        v_m_p1_m12[5] = 1.0/np.sqrt(6)
        v_m_p1_m12[6] = -2.0/np.sqrt(6)
        
        # Construct Matrix (Columns are the basis vectors)
        # Order of columns matches the target states |000>...|111>
        U = np.column_stack([
            v_s_32,      # -> |000>
            v_s_12,      # -> |001>
            v_s_m12,     # -> |010>
            v_s_m32,     # -> |011>
            v_m_p0_12,   # -> |100>
            v_m_p0_m12,  # -> |101>
            v_m_p1_12,   # -> |110>
            v_m_p1_m12   # -> |111>
        ])
        
        # Validate Unitary
        assert np.allclose(U.conj().T @ U, np.eye(8)), "Matrix construction failed unitarity check!"
        return Operator(U)

    def get_circuit(self):
        qc = QuantumCircuit(3, name="SchurTransform")
        qc.append(self.matrix, [0, 1, 2]) # Qiskit qubit ordering is usually reversed in visualization, but [0,1,2] here maps logical
        return qc

def demo_schur_sampling():
    print("=== Schur Sampling Demo (N=3) ===")
    
    # 1. Setup
    st = SchurTransformN3()
    schur_gate = st.get_circuit()
    sim = AerSimulator()
    
    # 2. Create a Test State
    # Let's create a state that is a mix of Symmetric and Mixed
    # State: |Psi> = 1/sqrt(2) |000> + 1/sqrt(2) |010>
    # |000> is fully Symmetric.
    # |010> is a superposition of Symmetric and Mixed.
    
    qc = QuantumCircuit(3, 3)
    
    # Prepare |010> + |000> (unnormalized for a sec) -> H on q1? No.
    # Let's just create a noisy looking state: H on all qubits
    qc.h([0, 1, 2]) 
    
    print("Input State: Equal Superposition (H^3 |000>)")
    print("Theory: This state is mostly Symmetric, but has Mixed components.")
    
    # 3. Apply Schur Transform (Change Basis)
    # Note: Qiskit applies unitary to qubits. 
    # Our matrix assumes q2 is MSB. Qiskit usually treats q2 as MSB in statevector, 
    # but let's be careful with ordering. We pass [0,1,2].
    qc.append(schur_gate, [0, 1, 2])
    
    # 4. Measure
    # We measure all 3 to see the full structure
    qc.measure([0, 1, 2], [0, 1, 2])
    
    # 5. Run
    qc = transpile(qc, sim)
    result = sim.run(qc, shots=10000).result()
    counts = result.get_counts()
    
    # 6. Analyze Results
    print("\nResults (Output bitstring: q2 q1 q0)")
    print("q2=0: Symmetric Sector")
    print("q2=1: Mixed Sector")
    
    sym_counts = 0
    mixed_counts = 0
    
    sorted_counts = dict(sorted(counts.items()))
    
    print("\nDetailed Counts:")
    for k, v in sorted_counts.items():
        # k is string 'q2q1q0'
        sector = "Symmetric" if k[0] == '0' else "Mixed    "
        print(f"State |{k}> ({sector}): {v}")
        
        if k[0] == '0': sym_counts += v
        else: mixed_counts += v
            
    print("-" * 30)
    print(f"Total Symmetric (Should be high): {sym_counts/100:.1f}%")
    print(f"Total Mixed     (Should be low):  {mixed_counts/100:.1f}%")
    
    # Theoretical Check for H^3 |000>:
    # P(Sym) for uniform superposition of 3 qubits is 100%? 
    # Wait, |+>|+>|+> is actually fully Symmetric (J=3/2, m_x=3/2).
    # So we should see 100% Symmetric!
    
    # Let's try a state that definitely has mixed component: |010>
    print("\n--- Test 2: Input |010> ---")
    qc2 = QuantumCircuit(3, 3)
    qc2.x(1) # |010>
    qc2.append(schur_gate, [0, 1, 2])
    qc2.measure([0, 1, 2], [0, 1, 2])
    counts2 = sim.run(transpile(qc2, sim), shots=10000).result().get_counts()
    
    sym2 = sum(v for k,v in counts2.items() if k[0]=='0')
    mix2 = sum(v for k,v in counts2.items() if k[0]=='1')
    
    print(f"Input |010> -> Symmetric: {sym2/100:.1f}%")
    print(f"Input |010> -> Mixed:     {mix2/100:.1f}%")
    print("(Theory: |010> has overlap 1/3 with Sym, 2/3 with Mixed)")

if __name__ == "__main__":
    demo_schur_sampling()