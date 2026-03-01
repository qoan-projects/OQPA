from typing import List, Optional
from qiskit import QuantumCircuit, transpile
from qiskit.providers import Backend
import os

class TranspilerService:
    def __init__(self, backend: Backend, optimization_level: int = 3, num_processes: Optional[int] = None):
        self.backend = backend
        self.optimization_level = optimization_level
        self.num_processes = num_processes if num_processes is not None else self._get_num_processes()

    def _get_num_processes(self) -> int:
        try:
            return len(os.sched_getaffinity(0))
        except AttributeError:
            return os.cpu_count() or 1

    def transpile(self, circuits: List[QuantumCircuit], skip: bool = False) -> List[QuantumCircuit]:
        if skip:
            return circuits
            
        return transpile(
            circuits, 
            backend=self.backend, 
            optimization_level=self.optimization_level, 
            num_processes=self.num_processes
        )
