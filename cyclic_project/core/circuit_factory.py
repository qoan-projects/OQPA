from core.strategies.base import CircuitGenerationStrategy
from core.strategies.dynamic import DynamicStrategy
from core.strategies.unrolled import UnrolledStrategy
from core.noise_models import NoiseStrategy

class CircuitFactory:
    @staticmethod
    def create_strategy(method: str, k: int, n_trials: int, n_registers: int) -> CircuitGenerationStrategy:
        if method == 'dynamic':
            return DynamicStrategy(k, n_trials, n_registers)
        elif method == 'unrolled':
            return UnrolledStrategy(k, n_trials, n_registers)
        else:
            raise ValueError(f"Unknown method: {method}")
