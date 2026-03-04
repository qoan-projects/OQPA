from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2 as AerSampler
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as IBMSampler, Batch
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeMarrakesh, FakeBrisbane

# Load environment variables from .env file
load_dotenv()

class BackendHandler(ABC):
    """
    Abstract interface for backend management.
    
    This class abstracts the details of connecting to different quantum backends 
    (Simulators, Fake Backends, Real Hardware) and providing a uniform way to get 
    backends and samplers.
    """
    @abstractmethod
    def get_backend(self):
        """
        Returns the backend object (e.g., AerSimulator or IBMBackend).
        """
        pass

    @abstractmethod
    def get_sampler(self, backend=None):
        """
        Returns a Sampler primitive configured for the backend.
        
        Args:
            backend: Optional backend instance.
        """
        pass

    def open_batch(self, backend=None):
        """
        Opens a Batch context manager for the backend.
        
        Args:
            backend: Optional backend instance.
            
        Returns:
            Batch context manager or None if not supported.
        """
        return None

class AERHandler(BackendHandler):
    """
    Handler for local AER simulation.
    
    Uses Qiskit Aer for high-performance local simulation.
    """
    def get_backend(self):
        """Returns a standard AerSimulator."""
        return AerSimulator()
    
    def get_sampler(self, backend=None):
        """Returns a SamplerV2 optimized for Aer."""
        # AerSampler doesn't strictly need a backend passed to init if generic, 
        # but passing it ensures consistency if we customized the simulator.
        return AerSampler()

class FakeBackendHandler(BackendHandler):
    """
    Handler for local simulation using Fake Backends (noise models from real hardware).
    
    Supported backends: 'fake_sherbrooke', 'fake_marrakesh', 'fake_brisbane'.
    """
    def __init__(self, backend_name="fake_sherbrooke"):
        """
        Args:
            backend_name (str): Name of the fake backend to instantiate.
        """
        self.backend_name = backend_name.lower()

    def get_backend(self):
        """Returns the specified Fake Backend instance."""
        if "sherbrooke" in self.backend_name:
            return FakeSherbrooke()
        elif "marrakesh" in self.backend_name:
            return FakeMarrakesh()
        elif "brisbane" in self.backend_name:
            return FakeBrisbane()
        else:
            # Fallback: Try to fetch real backend properties from IBM and create an AerSimulator
            print(f"Note: '{self.backend_name}' not found in standard Fake Providers.")
            print(f"Attempting to fetch device properties from IBM Runtime to create a noise model...")
            try:
                # We need a temporary service connection just to get backend properties
                # Reusing IBMRuntimeHandler logic or creating a service directly
                token = os.getenv("IBM_API") or os.getenv("IBM_QUANTUM_TOKEN")
                # Simple check to see if we can connect
                if token:
                    service = QiskitRuntimeService(channel="ibm_cloud", token=token)
                    real_backend = service.backend(self.backend_name)
                    print(f"Successfully fetched properties for '{self.backend_name}'. Creating AerSimulator.")
                    return AerSimulator.from_backend(real_backend)
                else:
                     print("Error: No IBM API token found to fetch backend properties.")
            except Exception as e:
                print(f"Failed to create fake backend from real device: {e}")
                
            print(f"Warning: Defaulting to FakeSherbrooke as fallback.")
            return FakeSherbrooke()

    def get_sampler(self, backend=None):
        """Returns an IBMSampler configured with the fake backend."""
        if backend is None:
            backend = self.get_backend()
        return IBMSampler(mode=backend)

class IBMRuntimeHandler(BackendHandler):
    """
    Handler for execution on real IBM Quantum hardware.
    
    Manages authentication via IBM Quantum Token or IBM Cloud CRN.
    """
    def __init__(self, backend_name="ibm_brisbane", channel=None, instance=None, token=None):
        """
        Args:
            backend_name (str): Name of the IBM Quantum system.
            channel (str, optional): 'ibm_quantum' or 'ibm_cloud'. Auto-detected if not provided.
            instance (str, optional): Service instance (CRN) or Hub/Group/Project.
            token (str, optional): API Token. Auto-loaded from .env if not provided.
        """
        self.backend_name = backend_name
        self.token = token or os.getenv("IBM_API") or os.getenv("IBM_QUANTUM_TOKEN")
        
        # Determine Channel and Instance logic
        crn = os.getenv("CRN")
        if crn and not instance:
            # If CRN is available and no instance specified, assume IBM Cloud
            self.channel = channel or "ibm_cloud"
            self.instance = crn
        else:
            # Default to IBM Quantum (Platform)
            self.channel = channel or "ibm_quantum"
            self.instance = instance

        self._service = None

    def _get_service(self):
        """Lazy initialization of the QiskitRuntimeService."""
        if self._service is None:
            print(f"Connecting to IBM Runtime Service via channel='{self.channel}'...")
            if self.instance:
                self._service = QiskitRuntimeService(channel=self.channel, token=self.token, instance=self.instance)
            else:
                self._service = QiskitRuntimeService(channel=self.channel, token=self.token)
        return self._service

    def get_backend(self):
        """Returns the real backend object from the service."""
        service = self._get_service()
        return service.backend(self.backend_name)

    def get_sampler(self, backend=None):
        """Returns an IBMSampler configured for the real backend."""
        # Check if we are inside a Batch context?
        # The caller should instantiate Sampler with mode=batch
        # But here we just return a default sampler if no batch provided.
        if backend is None:
            backend = self.get_backend()
        return IBMSampler(mode=backend)

    def open_batch(self, backend=None):
        """
        Opens a Batch context manager for the IBM backend.
        """
        if backend is None:
            backend = self.get_backend()
        return Batch(backend=backend)
