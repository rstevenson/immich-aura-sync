"""Configuration management from YAML file"""
import os
import yaml
from pathlib import Path
from typing import Optional
from loguru import logger


class Config:
    """Application configuration from YAML file"""
    
    # Immich settings
    IMMICH_URL: str
    IMMICH_API_KEY: str
    IMMICH_ALBUM_ID: str
    
    # Aura settings
    AURA_EMAIL: str
    AURA_PASSWORD: str
    AURA_FRAME_ID: str
    
    # Sync settings
    SYNC_INTERVAL_MINUTES: int = 15
    IMMICH_TAG_NAME: str = "synced-to-aura"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    @classmethod
    def load(cls, config_path: str = "config.yml") -> None:
        """
        Load and validate configuration from YAML file
        
        Args:
            config_path: Path to YAML config file (default: config.yml)
        """
        
        # Check if config file exists
        if not Path(config_path).exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create it from the template: cp config.example.yml config.yml"
            )
        
        # Load YAML
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            raise ValueError(f"Config file {config_path} is empty")
        
        # Load Immich settings
        immich_config = config_data.get('immich', {})
        cls.IMMICH_URL = cls._get_required(immich_config, 'url', 'immich.url')
        cls.IMMICH_API_KEY = cls._get_required(immich_config, 'api_key', 'immich.api_key')
        cls.IMMICH_ALBUM_ID = cls._get_required(immich_config, 'album_id', 'immich.album_id')
        
        # Load Aura settings
        aura_config = config_data.get('aura', {})
        cls.AURA_EMAIL = cls._get_required(aura_config, 'email', 'aura.email')
        cls.AURA_PASSWORD = cls._get_required(aura_config, 'password', 'aura.password')
        cls.AURA_FRAME_ID = cls._get_required(aura_config, 'frame_id', 'aura.frame_id')
        
        # Load sync settings (optional with defaults)
        sync_config = config_data.get('sync', {})
        cls.SYNC_INTERVAL_MINUTES = sync_config.get('interval_minutes', 15)
        cls.IMMICH_TAG_NAME = sync_config.get('tag_name', 'synced-to-aura')
        
        # Load logging settings (optional with defaults)
        logging_config = config_data.get('logging', {})
        cls.LOG_LEVEL = logging_config.get('level', 'INFO').upper()
        
        # Validate
        cls._validate()
        
        logger.info("Configuration loaded successfully")
        logger.debug(f"Immich URL: {cls.IMMICH_URL}")
        logger.debug(f"Immich Album ID: {cls.IMMICH_ALBUM_ID}")
        logger.debug(f"Aura Frame ID: {cls.AURA_FRAME_ID}")
        logger.debug(f"Sync Interval: {cls.SYNC_INTERVAL_MINUTES} minutes")
        logger.debug(f"Tag Name: {cls.IMMICH_TAG_NAME}")
    
    @staticmethod
    def _get_required(config_dict: dict, key: str, full_path: str) -> str:
        """Get required config value or raise error"""
        value = config_dict.get(key)
        if not value:
            raise ValueError(f"Missing required configuration: {full_path}")
        return str(value)
    
    @classmethod
    def _validate(cls) -> None:
        """Validate configuration values"""
        
        # Validate sync interval
        if cls.SYNC_INTERVAL_MINUTES < 1:
            raise ValueError("sync.interval_minutes must be at least 1")
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if cls.LOG_LEVEL not in valid_levels:
            raise ValueError(f"logging.level must be one of: {', '.join(valid_levels)}")
        
        # Ensure Immich URL ends with /api
        if not cls.IMMICH_URL.endswith("/api"):
            logger.warning("immich.url should end with /api, you may encounter issues")
