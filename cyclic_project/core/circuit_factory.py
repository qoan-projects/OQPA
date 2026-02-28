from core.strategies.base import CircuitGenerationStrategy
from core.strategies.dynamic import DynamicStrategy
from core.strategies.unrolled import UnrolledStrategy
from core.noise_models import NoiseStrategy

class CircuitFactory:
    @staticmethod
    def create_strategy(method: str, k: int, n_trials: int, n_registers: int, **kwargs) -> CircuitGenerationStrategy:
        if method == 'dynamic':
            return DynamicStrategy(k, n_trials, n_registers)
        elif method == 'unrolled':
            no_reset = kwargs.get('no_reset', False)
            return UnrolledStrategy(k, n_trials, n_registers, no_reset=no_reset)
        elif method == 'parameterized':
            # Parameterized uses Unrolled strategy to build the base circuit
            # The difference is only in the noise strategy applied later
            no_reset = kwargs.get('no_reset', False)
            return UnrolledStrategy(k, n_trials, n_registers, no_reset=no_reset)
        else:
            raise ValueError(f"Unknown method: {method}")
