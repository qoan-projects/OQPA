from qiskit import QuantumCircuit, QuantumRegister

def apply_schur_test(qc: QuantumCircuit, ancilla, reg_a, reg_b, k: int):
    """
    Performs a Schur test (swap test) between two registers controlled by an ancilla.
    
    Args:
        qc: QuantumCircuit to modify.
        ancilla: Control qubit (or index/register).
        reg_a: First register (or list of qubits).
        reg_b: Second register (or list of qubits).
        k: Number of qubits to swap.
    """
    qc.h(ancilla)
    for i in range(k):
        qc.cswap(ancilla, reg_a[i], reg_b[i])
    qc.h(ancilla)

def apply_cyclic_rotation(qc: QuantumCircuit, regs: list, k: int):
    """
    Performs a cyclic permutation of the given registers (physical swap).
    Rotates regs[0] -> regs[1] -> ... -> regs[N-1] -> regs[0]?
    
    Based on original code:
    for i in range(k):
        for j in range(N-1, 0, -1):
            qc.swap(regs[j][i], regs[j-1][i])
            
    This rotates Right to Left? 
    regs[0] goes to regs[1]... no.
    j goes from N-1 down to 1.
    swap(N-1, N-2)
    swap(N-2, N-3)
    ...
    swap(1, 0)
    
    Effect: regs[0] moves to regs[N-1]. regs[1] moves to regs[0], etc.
    This is a Left Rotation.
    """
    N = len(regs)
    for i in range(k):
        for j in range(N-1, 0, -1):
            qc.swap(regs[j][i], regs[j-1][i])

def apply_cyclic_rotation_indices(qc: QuantumCircuit, indices: list, k: int):
    """
    Applies physical SWAP gates to rotate data among the specified register indices.
    
    Args:
        qc: Circuit.
        indices: List of register indices involved in the rotation.
        k: Qubits per register.
    """
    # Apply SWAP gates to physically rotate the states in the registers
    for i in range(len(indices)-1, 0, -1):
        idx_j = indices[i]
        idx_j_minus_1 = indices[i-1]
        
        # Swap full registers
        for b in range(k):
            q_j = qc.qubits[idx_j*k + b]
            q_j_1 = qc.qubits[idx_j_minus_1*k + b]
            qc.swap(q_j, q_j_1)
