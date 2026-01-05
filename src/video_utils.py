"""Video utilities for extracting metadata"""
import json
import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger


def get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using ffprobe
    
    Args:
        video_path: Path to video file
        
    Returns:
        Duration in seconds as float
        
    Raises:
        subprocess.CalledProcessError: If ffprobe fails
        FileNotFoundError: If ffprobe not installed
        ValueError: If duration cannot be parsed
    """
    try:
        result = subprocess.run([
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ], capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        
        logger.debug(f"Video duration for {video_path}: {duration}s")
        return duration
        
    except FileNotFoundError:
        logger.error("ffprobe not found. Please install ffmpeg.")
        raise
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse video duration: {e}")
        raise ValueError(f"Could not determine duration for {video_path}") from e


def is_video(mime_type: str, file_extension: str) -> bool:
    """
    Determine if an asset is a video based on MIME type or extension
    
    Args:
        mime_type: MIME type string (e.g., "video/mp4")
        file_extension: File extension (e.g., ".mp4")
        
    Returns:
        True if asset is a video, False otherwise
    """
    # Check MIME type
    if mime_type and mime_type.startswith('video/'):
        return True
    
    # Check extension as fallback
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv'}
    if file_extension.lower() in video_extensions:
        return True
    
    return False
