import json
import getpass
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Manages secure storage and retrieval of user configuration."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config manager.
        
        Args:
            config_dir: Optional custom config directory. Defaults to ~/.config/mcp-transport
        """
        if config_dir is None:
            config_dir = Path.home() / ".config" / "mcp-transport"
        
        self.config_dir = config_dir
        self.config_file = config_dir / "config.json"
    
    def get_github_pat(self) -> str:
        """
        Retrieve GitHub Personal Access Token from config or prompt user.
        
        Returns:
            GitHub Personal Access Token
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    pat = config.get("GITHUB_PERSONAL_ACCESS_TOKEN")
                    if pat:
                        return pat
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Config doesn't exist or PAT not found, prompt user
        print("GitHub Personal Access Token not found in configuration.")
        print("Please enter your GitHub PAT (it will be stored securely):")
        pat = getpass.getpass("GitHub PAT: ")
        
        # Save to config
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config = {"GITHUB_PERSONAL_ACCESS_TOKEN": pat}
        
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        # Set restrictive permissions (Unix-like systems)
        if hasattr(self.config_file, "chmod"):
            self.config_file.chmod(0o600)
        
        print(f"Configuration saved to {self.config_file}")
        return pat
    
    def get_config(self) -> dict:
        """Retrieve entire config dictionary."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def update_config(self, updates: dict) -> None:
        """Update configuration with new values."""
        config = self.get_config()
        config.update(updates)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        if hasattr(self.config_file, "chmod"):
            self.config_file.chmod(0o600)

