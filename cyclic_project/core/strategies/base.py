from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.noise_models import NoiseStrategy

class CircuitGenerationStrategy(ABC):
    def __init__(self, k: int, n_trials: int, n_registers: int):
        self.k = k
        self.n_trials = n_trials
        self.n_registers = n_registers
        self.noise_strategy: Optional[NoiseStrategy] = None

    def set_noise_strategy(self, strategy: NoiseStrategy):
        self.noise_strategy = strategy

    @abstractmethod
    def build(self, epsilon: float) -> List[Dict[str, Any]]:
        pass
