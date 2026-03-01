from typing import List
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit

class QPARegisters:
    """
    Manages the quantum and classical registers for the QPA protocol.
    Provides abstraction over direct index manipulation.
    """
    def __init__(self, n_registers: int, k: int, n_trials: int, use_ancilla_pool: bool = False, no_reset: bool = False):
        self.n = n_registers
        self.k = k
        self.n_trials = n_trials
        self.no_reset = no_reset
        
        # Data Registers
        self.qr_data = [QuantumRegister(k, f"R{i+1}") for i in range(n_registers)]
        
        # Ancilla handling depends on method (Dynamic vs Unrolled)
        self.qr_ancilla = []
        self.cr_ancilla = None
        self.cr_readout = ClassicalRegister(k, "readout")
        
        self.use_ancilla_pool = use_ancilla_pool
        
        if use_ancilla_pool:
            # For Unrolled: Pool of ancillas reused
            num_concurrent_tests = n_registers // 2
            
            if no_reset:
                # If no_reset, we need separate ancillas for each trial
                # Total ancillas = num_concurrent_tests * n_trials
                total_ancillas = num_concurrent_tests * n_trials
                self.qr_ancilla = [QuantumRegister(1, f"anc_{i}") for i in range(total_ancillas)]
            else:
                # If reset, we reuse the same set of ancillas
                self.qr_ancilla = [QuantumRegister(1, f"anc_{i}") for i in range(num_concurrent_tests)]
                
            max_total_measurements = n_trials * (n_registers // 2)
            self.cr_ancilla = ClassicalRegister(max_total_measurements, "anc_meas")
        else:
            # For Dynamic: Specific registers
            max_parallel_tests = (n_registers - 1) // 2
            self.qr_ctrl_par = QuantumRegister(max_parallel_tests, "ctrl_par")
            self.qr_ctrl_rec = QuantumRegister(1, "ctrl_rec")
            self.qr_ancilla = [self.qr_ctrl_par, self.qr_ctrl_rec]
            
            # Classical pools
            self.cr_pool = [ClassicalRegister(max_parallel_tests, f"res_t{t}") for t in range(n_trials)]
            self.cr_rec = ClassicalRegister(n_trials, "res_rec")

    def get_data_register(self, idx: int) -> QuantumRegister:
        return self.qr_data[idx]

    def get_reserve(self) -> QuantumRegister:
        return self.qr_data[self.n - 1]

    def get_circuit_registers(self) -> List:
        regs = [*self.qr_data]
        if self.use_ancilla_pool:
            regs.extend(self.qr_ancilla)
            regs.append(self.cr_readout)
            regs.append(self.cr_ancilla)
        else:
            regs.extend(self.qr_ancilla)
            regs.extend(self.cr_pool)
            regs.append(self.cr_rec)
            regs.append(self.cr_readout)
        return regs
