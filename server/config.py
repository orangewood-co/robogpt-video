"""
Configuration management for the video streaming system.
"""
import os
import yaml
from typing import Dict, Any


class Config:
    """Central configuration management."""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to config.yaml file. Defaults to ../config.yaml
        """
        if config_path is None:
            # Default to config.yaml in project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config.yaml')

        self.config_path = config_path
        self._config = self._load_config()
        self._apply_env_overrides()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            return self._get_default_config()

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config else self._get_default_config()
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            print("Using default configuration")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            'streams': {
                'timeout_seconds': 300,  # 5 minutes
                'max_concurrent': 50,
                'max_buffer_frames': 30
            },
            'recording': {
                'enabled': True,
                'codec': 'mp4v',
                'fps': 30,
                'retention_days': 7
            },
            'cleanup': {
                'interval_seconds': 60,
                'schedule_time': '03:00'
            },
            'server': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'cors_enabled': True,
                'max_frame_size_mb': 10
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }

    def _apply_env_overrides(self):
        """Override config values from environment variables."""
        env_mappings = {
            'STREAM_TIMEOUT_SECONDS': ('streams', 'timeout_seconds', int),
            'MAX_CONCURRENT_STREAMS': ('streams', 'max_concurrent', int),
            'RECORDING_RETENTION_DAYS': ('recording', 'retention_days', int),
            'LOG_LEVEL': ('logging', 'level', str),
            'SERVER_PORT': ('server', 'port', int),
            'SERVER_DEBUG': ('server', 'debug', lambda x: x.lower() == 'true')
        }

        for env_var, (section, key, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    self._config[section][key] = converter(value)
                except (ValueError, KeyError) as e:
                    print(f"Warning: Failed to apply env override {env_var}: {e}")

    def get(self, section: str, key: str, default=None):
        """
        Get configuration value.

        Args:
            section: Config section name
            key: Config key name
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        try:
            return self._config[section][key]
        except KeyError:
            return default

    @property
    def stream_timeout(self) -> int:
        """Get stream inactivity timeout in seconds."""
        return self.get('streams', 'timeout_seconds', 300)

    @property
    def max_concurrent_streams(self) -> int:
        """Get maximum concurrent streams."""
        return self.get('streams', 'max_concurrent', 50)

    @property
    def max_buffer_frames(self) -> int:
        """Get maximum frames to buffer per stream."""
        return self.get('streams', 'max_buffer_frames', 30)

    @property
    def recording_enabled(self) -> bool:
        """Check if recording is enabled."""
        return self.get('recording', 'enabled', True)

    @property
    def recording_codec(self) -> str:
        """Get recording codec."""
        return self.get('recording', 'codec', 'mp4v')

    @property
    def recording_fps(self) -> int:
        """Get recording FPS."""
        return self.get('recording', 'fps', 30)

    @property
    def retention_days(self) -> int:
        """Get recording retention days."""
        return self.get('recording', 'retention_days', 7)

    @property
    def cleanup_interval(self) -> int:
        """Get cleanup check interval in seconds."""
        return self.get('cleanup', 'interval_seconds', 60)

    @property
    def cleanup_schedule_time(self) -> str:
        """Get scheduled cleanup time."""
        return self.get('cleanup', 'schedule_time', '03:00')

    @property
    def server_host(self) -> str:
        """Get server host."""
        return self.get('server', 'host', '0.0.0.0')

    @property
    def server_port(self) -> int:
        """Get server port."""
        return self.get('server', 'port', 5000)

    @property
    def server_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self.get('server', 'debug', False)

    @property
    def cors_enabled(self) -> bool:
        """Check if CORS is enabled."""
        return self.get('server', 'cors_enabled', True)

    @property
    def max_frame_size_bytes(self) -> int:
        """Get maximum frame size in bytes."""
        max_mb = self.get('server', 'max_frame_size_mb', 10)
        return max_mb * 1024 * 1024

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get('logging', 'level', 'INFO')

    @property
    def log_format(self) -> str:
        """Get logging format."""
        return self.get('logging', 'format',
                       '%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Global config instance
config = Config()
