import yaml
import os
from src.models import SystemConfig

def load_config(config_path: str = "system_config.yaml") -> SystemConfig:
    """Loads the system configuration from a YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)
        
    return SystemConfig(**config_data)
