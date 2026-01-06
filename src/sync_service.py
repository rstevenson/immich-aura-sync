"""Sync service for Immich to Aura Frame"""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from loguru import logger

# Add auraframes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from auraframes.aura import Aura
from auraframes.models.asset import Asset

from config import Config
from immich_client import ImmichClient


class SyncService:
    """Service for syncing Immich assets to Aura Frame"""
    
    def __init__(self):
        """Initialize sync service with Immich and Aura clients"""
        self.immich = ImmichClient(Config.IMMICH_URL, Config.IMMICH_API_KEY)
        self.aura = Aura()
        
        
        # Get or create the sync tag
        self.sync_tag_id = self.immich.get_or_create_tag(Config.IMMICH_TAG_NAME)
        logger.info(f"Using tag '{Config.IMMICH_TAG_NAME}' (ID: {self.sync_tag_id})")
        
        logger.info("Sync service initialized")
    
    def sync_album(self) -> Dict[str, int]:
        """
        Sync untagged assets from configured Immich album to Aura frame
        
        Returns:
            Dict with counts: {"uploaded": int, "failed": int}
        """
        stats = {"uploaded": 0, "failed": 0}
        uploaded_asset_ids = []
        
        try:
            # Get untagged assets from album using search API
            assets = self.immich.search_untagged_album_assets(Config.IMMICH_ALBUM_ID)
            logger.info(f"Found {len(assets)} unsynced assets in album")
            
            if not assets:
                logger.info("No new assets to sync")
                return stats
            
            # Login to Aura
            self.aura.login(Config.AURA_EMAIL, Config.AURA_PASSWORD)
            
            # Process each untagged asset
            for asset_data in assets:
                asset_id = asset_data.get('id')
                
                try:
                    self._process_asset(asset_data)
                    stats["uploaded"] += 1
                    uploaded_asset_ids.append(asset_id)
                except Exception as e:
                    logger.error(f"Failed to process asset {asset_id}: {e}")
                    stats["failed"] += 1
            
            # Tag successfully uploaded assets
            if uploaded_asset_ids:
                try:
                    self.immich.tag_assets(self.sync_tag_id, uploaded_asset_ids)
                    logger.info(f"Tagged {len(uploaded_asset_ids)} assets with '{Config.IMMICH_TAG_NAME}'")
                except Exception as e:
                    logger.error(f"Failed to tag assets: {e}")
            
            logger.info(f"Sync complete: {stats['uploaded']} uploaded, {stats['failed']} failed")
            
        except Exception as e:
            logger.error(f"Failed to sync album: {e}")
            raise
        
        return stats
    
    def _process_asset(self, asset_data: Dict[str, Any]) -> None:
        """
        Process and upload a single asset
        
        Args:
            asset_data: Asset metadata from Immich API
        """
        asset_id = asset_data['id']
        asset_type = asset_data.get('type', 'IMAGE')
        original_filename = asset_data.get('originalFileName', 'unknown')
        mime_type = asset_data.get('originalMimeType', '')
        file_extension = Path(original_filename).suffix
        
        logger.info(f"Processing {asset_type}: {original_filename}")
        
        # Create temp directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            if self._is_video(mime_type, file_extension):
                self._upload_video(asset_data, temp_path)
            else:
                self._upload_photo(asset_data, temp_path)
    
    def _upload_photo(self, asset_data: Dict[str, Any], temp_path: Path) -> None:
        """
        Upload a photo to Aura frame
        
        Args:
            asset_data: Asset metadata from Immich
            temp_path: Temporary directory for downloads
        """
        asset_id = asset_data['id']
        original_filename = asset_data.get('originalFileName', 'photo.jpg')
        
        # Download photo
        photo_path = temp_path / original_filename
        self.immich.download_asset(asset_id, str(photo_path))
        
        # Create Aura asset
        aura_asset = self._create_aura_asset(asset_data)
        
        # Upload to Aura
        logger.debug(f"Uploading photo to Aura: {original_filename}")
        self.aura.upload_image(Config.AURA_FRAME_ID, str(photo_path), aura_asset)
        logger.info(f"Successfully uploaded photo: {original_filename}")
    
    def _upload_video(self, asset_data: Dict[str, Any], temp_path: Path) -> None:
        """
        Upload a video to Aura frame
        
        Args:
            asset_data: Asset metadata from Immich
            temp_path: Temporary directory for downloads
        """
        asset_id = asset_data['id']
        original_filename = asset_data.get('originalFileName', 'video.mp4')
        
        # Download video
        video_path = temp_path / original_filename
        self.immich.download_asset(asset_id, str(video_path))
        
        # Download thumbnail for poster
        poster_path = temp_path / f"{asset_id}_poster.jpg"
        self.immich.download_thumbnail(asset_id, str(poster_path))
        
        # Get video duration from Immich metadata (format: "0:00:06.57")
        duration_str = asset_data.get('duration', '0:00:00.00')
        duration = self._parse_duration(duration_str)
        
        # Create Aura asset
        aura_asset = self._create_aura_asset(asset_data)
        
        # Upload to Aura
        logger.debug(f"Uploading video to Aura: {original_filename} (duration: {duration}s)")
        self.aura.upload_video(
            Config.AURA_FRAME_ID,
            str(video_path),
            str(poster_path),
            duration,
            aura_asset
        )
        logger.info(f"Successfully uploaded video: {original_filename}")
    
    def _parse_duration(self, duration_str: str) -> float:
        """
        Parse Immich duration string to seconds
        
        Args:
            duration_str: Duration in format "H:MM:SS.ms" (e.g., "0:00:06.57")
            
        Returns:
            Duration in seconds as float
        """
        try:
            parts = duration_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return total_seconds
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse duration '{duration_str}', using 0: {e}")
            return 0.0
    
    def _create_aura_asset(self, asset_data: Dict[str, Any]) -> Asset:
        """
        Create an Aura Asset object from Immich asset data
        
        Args:
            asset_data: Asset metadata from Immich
            
        Returns:
            Aura Asset object
        """
        local_identifier = f"immich_{asset_data['id']}"
        taken_at = asset_data.get('fileCreatedAt', datetime.now().isoformat())
        
        return Asset(
            local_identifier=local_identifier,
            taken_at=taken_at,
            selected=True,
            upload_priority=10,
            favorite=asset_data.get('isFavorite', False),
            rotation_cw=0,
            hdr=False,
            panorama=False,
        )
    
    @staticmethod
    def _is_video(mime_type: str, file_extension: str) -> bool:
        """
        Determine if an asset is a video
        
        Args:
            mime_type: MIME type string
            file_extension: File extension
            
        Returns:
            True if asset is a video
        """
        if mime_type and mime_type.startswith('video/'):
            return True
        
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv'}
        return file_extension.lower() in video_extensions
