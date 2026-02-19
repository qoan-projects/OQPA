import os
import pandas as pd
from typing import Optional

class PathManager:
    """
    Centralizes the logic for constructing directory paths for jobs, logs, and results.
    """
    
    @staticmethod
    def get_project_root() -> str:
        """Returns the absolute path to the project root."""
        # Assuming this file is in utils/paths.py, root is ../
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_job_directory(backend: str, 
                          device: str, 
                          n: int, 
                          k: int, 
                          trials: int, 
                          points: int, 
                          shots: int, 
                          n_random: int,
                          timestamp: Optional[str] = None) -> str:
        """
        Constructs the hierarchical job directory.
        
        Structure:
        data/jobs/<backend>/<device>/n<N>_k<K>_t<Trials>/p<Points>/s<Shots>_c<Random>/<timestamp>
        """
        root = PathManager.get_project_root()
        
        param_str = f"n{n}_k{k}_t{trials}"
        points_str = f"p{points}"
        config_str = f"s{shots}_c{n_random}"
        
        if timestamp is None:
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            
        path = os.path.join(root, "data", "jobs", backend, device, param_str, points_str, config_str, timestamp)
        return path

    @staticmethod
    def get_history_directory(job_dir: str) -> str:
        """
        Determines the history directory (pXX level) from a job directory.
        Expected job_dir: .../pXX/sXX_cXX/timestamp
        """
        try:
            parent_dir = os.path.dirname(job_dir) # .../sXX_cXX
            history_dir = os.path.dirname(parent_dir) # .../pXX
            if not os.path.basename(history_dir).startswith('p'):
                return job_dir
            return history_dir
        except:
            return job_dir

    @staticmethod
    def ensure_dir(path: str):
        """Ensures that the directory exists."""
        os.makedirs(path, exist_ok=True)
