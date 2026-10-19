"""
litrun: Universal Lightweight Embedded Linux AI Runtime
"""

from litrun.hardware import HardwareProfile, probe_hardware
from litrun.governor import GovernorStatus, poll_governor, check_ram_envelope
from litrun.model import Model
from litrun.registry import ModelEntry, ModelVariant, list_models, get_model

__version__ = "0.1.0"

__all__ = [
    "Model",
    "HardwareProfile",
    "probe_hardware",
    "GovernorStatus",
    "poll_governor",
    "check_ram_envelope",
    "ModelEntry",
    "ModelVariant",
    "list_models",
    "get_model",
    "__version__",
]

