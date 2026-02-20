import sys
from utils.config import parse_arguments
from execution.runner import SimulationRunner

def main():
    # Parse CLI arguments into a Configuration object
    config = parse_arguments()

    # Initialize Runner
    runner = SimulationRunner(config)

    # Execute Simulation
    runner.run()

if __name__ == "__main__":
    main()
