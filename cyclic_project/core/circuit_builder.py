from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from itertools import product
from core.noise_models import NoiseStrategy
from core.hybrid_topology import UnrolledHybridStrategy

class CircuitBuilder(ABC):
    """
    Abstract base class for building QPA circuits.
    
    This class defines the interface for creating quantum circuits used in the QPA protocol.
    It supports setting a noise strategy and must implement the `build` method.
    """
    def __init__(self, k: int, n_trials: int, n_registers: int = 5):
        """
        Initialize the CircuitBuilder.

        Args:
            k (int): Number of qubits per register.
            n_trials (int): Number of purification trials (depth of the protocol).
            n_registers (int, optional): Total number of registers available. Defaults to 5.
        """
        self.k = k
        self.n_trials = n_trials
        self.n_registers = n_registers
        self.noise_strategy: Optional[NoiseStrategy] = None

    def set_noise_strategy(self, strategy: NoiseStrategy):
        """
        Set the noise strategy to be applied during circuit construction.

        Args:
            strategy (NoiseStrategy): The noise strategy instance.
        """
        self.noise_strategy = strategy

    @abstractmethod
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        """
        Builds the circuits for the experiment.
        
        Args:
            epsilon (float): Noise parameter (e.g., depolarization probability).
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains:
                - 'circuit': The QuantumCircuit object.
                - 'conditions': A dictionary of expected measurement values (for post-selection).
                - 'metadata': Additional info (e.g., path name, type).
        """
        pass

class DynamicCircuitBuilder(CircuitBuilder):
    """
    Builds a single dynamic circuit (using if_test) for AER simulation.
    Ported from legacy/cyclid_method/qpa_engine.py.
    
    This builder uses Qiskit's dynamic circuit capabilities (control flow) to implement
    the QPA protocol in a single circuit with mid-circuit measurements and real-time branching.
    """
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        """
        Builds the dynamic circuit.

        Args:
            epsilon (float): Noise parameter.

        Returns:
            List[Dict[str, Any]]: A list containing a single dictionary with the dynamic circuit.
        """
        qr_data = [QuantumRegister(self.k, f"R{i+1}") for i in range(self.n_registers)]
        max_parallel_tests = (self.n_registers - 1) // 2
        qr_ctrl_par = QuantumRegister(max_parallel_tests, "ctrl_par")
        qr_ctrl_rec = QuantumRegister(1, "ctrl_rec") 
        cr_pool = [ClassicalRegister(max_parallel_tests, f"res_t{t}") for t in range(self.n_trials)]
        cr_rec = ClassicalRegister(self.n_trials, "res_rec")
        cr_final = ClassicalRegister(self.k, "readout")
        
        regs = [*qr_data, qr_ctrl_par, qr_ctrl_rec, *cr_pool, cr_rec, cr_final]
        qc = QuantumCircuit(*regs)
        
        # Apply Noise
        if self.noise_strategy and epsilon > 0:
            self.noise_strategy.apply_noise(qc, qr_data, epsilon)
        
        initial_reserve = qr_data[-1]
        initial_pairs = []
        for i in range(0, self.n_registers - 1, 2):
            initial_pairs.append((qr_data[i], qr_data[i+1]))
            
        self._build_recursive_layer(qc, initial_pairs, initial_reserve, 
                                    qr_ctrl_par, qr_ctrl_rec, 
                                    cr_pool, cr_rec, 0)
        
        qc.measure(initial_reserve, cr_final)
        
        return [{'circuit': qc, 'conditions': {}, 'metadata': {'type': 'dynamic'}}]

    def _build_recursive_layer(self, qc, current_pairs, reserve_reg, 
                               qr_par, qr_rec, cr_pool, cr_rec, current_trial):
        """
        Recursively builds layers of the QPA protocol using dynamic control flow.

        Args:
            qc (QuantumCircuit): The circuit being built.
            current_pairs (List): List of register pairs available for purification.
            reserve_reg (QuantumRegister): The current reserve register.
            qr_par (QuantumRegister): Control qubits for parallel tests.
            qr_rec (QuantumRegister): Control qubit for recursive recovery.
            cr_pool (List[ClassicalRegister]): Pool of classical registers for test results.
            cr_rec (ClassicalRegister): Classical register for recovery results.
            current_trial (int): Current depth/trial index.
        """
        if current_trial >= self.n_trials: return

        num_pairs = len(current_pairs)
        current_cr = cr_pool[current_trial]
        
        # 1. Parallel Schur Tests
        for i in range(num_pairs):
            self.schur_test(qc, qr_par[i], current_cr[i], current_pairs[i][0], current_pairs[i][1])

        # 2. Branching Logic
        outcomes = list(product([0, 1], repeat=num_pairs))
        
        for outcome in outcomes:
            conditions = [(current_cr[i], val) for i, val in enumerate(outcome)]
            
            def apply_conditions(cond_list, block_func):
                if not cond_list: block_func(); return
                head, *tail = cond_list
                with qc.if_test(head): apply_conditions(tail, block_func)

            def logic_block():
                # A. ALL SUCCESS
                if all(v == 0 for v in outcome):
                    all_regs = []
                    for p in current_pairs: all_regs.extend(p)
                    all_regs.append(reserve_reg)
                    self.cyclic_rotation(qc, all_regs)
                    self._build_recursive_layer(qc, current_pairs, reserve_reg, 
                                                qr_par, qr_rec, cr_pool, cr_rec, current_trial + 1)
                
                # B. SOME FAILURE
                else:
                    surviving_pairs = []
                    for i, val in enumerate(outcome):
                        if val == 0: surviving_pairs.append(current_pairs[i])
                    
                    num_survivors = len(surviving_pairs)
                    if num_survivors >= 1:
                        active_regs = []
                        for p in surviving_pairs: active_regs.extend(p)
                        active_regs.append(reserve_reg)
                        self.cyclic_rotation(qc, active_regs)
                        self._build_recursive_layer(qc, surviving_pairs, reserve_reg, 
                                                    qr_par, qr_rec, cr_pool, cr_rec, current_trial + 1)
                    else:
                        pass # All failed

            apply_conditions(conditions, logic_block)

    def schur_test(self, qc, ctrl, res_bit, reg_a, reg_b):
        """Performs a Schur test (swap test) between two registers."""
        qc.reset(ctrl)
        qc.h(ctrl)
        for i in range(self.k):
            qc.cswap(ctrl, reg_a[i], reg_b[i])
        qc.h(ctrl)
        qc.measure(ctrl, res_bit)
        return res_bit

    def cyclic_rotation(self, qc, regs):
        """Performs a cyclic permutation of the given registers."""
        k = self.k
        N = len(regs)
        for i in range(k):
            for j in range(N-1, 0, -1):
                qc.swap(regs[j][i], regs[j-1][i])

class UnrolledCircuitBuilder(CircuitBuilder):
    """
    Builds a set of static circuits representing all execution paths.
    Wraps UnrolledHybridStrategy.
    
    This builder is suitable for hardware or backends that do not support dynamic circuits well.
    It generates a separate circuit for every possible valid path through the probabilistic decision tree.
    """
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        """
        Builds the list of unrolled circuits.

        Args:
            epsilon (float): Noise parameter.

        Returns:
            List[Dict[str, Any]]: List of circuit dictionaries with 'conditions' for post-selection.
        """
        strategy = UnrolledHybridStrategy(self.k, self.n_trials, self.n_registers)
        circuits_data = strategy.generate_all_paths(epsilon, self.noise_strategy)
        
        # Add metadata
        for item in circuits_data:
            item['metadata'] = {'type': 'unrolled'}
            
        return circuits_data
