"""Immich API client"""
import requests
from typing import List, Dict, Any, Optional
from loguru import logger


class ImmichClient:
    """Client for interacting with Immich API"""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Immich client
        
        Args:
            base_url: Immich API base URL (e.g., http://immich:2283/api)
            api_key: Immich API key with required permissions
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "x-api-key": api_key,
            "Accept": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def search_untagged_album_assets(self, album_id: str) -> List[Dict[str, Any]]:
        """
        Search for assets in an album that don't have any tags
        
        Args:
            album_id: Album UUID
            
        Returns:
            List of untagged asset dictionaries from the album
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/search/metadata"
        
        # Use search API with albumIds filter and tagIds: null to get untagged assets
        payload = {
            "albumIds": [album_id],
            "tagIds": None,  # null = assets with no tags
            "size": 1000,  # Max page size
            "page": 1
        }
        
        all_assets = []
        
        try:
            while True:
                response = self.session.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                assets = result.get('assets', {}).get('items', [])
                
                if not assets:
                    break
                
                all_assets.extend(assets)
                
                # Check if there are more pages
                total = result.get('assets', {}).get('total', 0)
                if len(all_assets) >= total or payload['page'] * payload['size'] >= total:
                    break
                
                payload['page'] += 1
            
            logger.debug(f"Found {len(all_assets)} untagged assets in album {album_id}")
            return all_assets
            
        except requests.RequestException as e:
            logger.error(f"Failed to search album assets: {e}")
            raise
    
    def download_asset(self, asset_id: str, output_path: str) -> None:
        """
        Download original asset file
        
        Args:
            asset_id: Asset UUID
            output_path: Path to save the downloaded file
            
        Raises:
            requests.RequestException: If download fails
        """
        url = f"{self.base_url}/assets/{asset_id}/original"
        
        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.debug(f"Downloaded asset {asset_id} to {output_path}")
            
        except requests.RequestException as e:
            logger.error(f"Failed to download asset {asset_id}: {e}")
            raise
    
    def download_thumbnail(self, asset_id: str, output_path: str) -> None:
        """
        Download asset thumbnail (used as video poster)
        
        Args:
            asset_id: Asset UUID
            output_path: Path to save the thumbnail
            
        Raises:
            requests.RequestException: If download fails
        """
        # Use thumbnail endpoint for poster frame
        url = f"{self.base_url}/assets/{asset_id}/thumbnail"
        
        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.debug(f"Downloaded thumbnail for asset {asset_id} to {output_path}")
            
        except requests.RequestException as e:
            logger.error(f"Failed to download thumbnail for asset {asset_id}: {e}")
            raise
    
    def get_or_create_tag(self, tag_name: str) -> str:
        """
        Get existing tag by name or create if it doesn't exist
        
        Args:
            tag_name: Name of the tag
            
        Returns:
            Tag ID
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/tags"
        
        try:
            # Try to get existing tags
            response = self.session.get(url)
            response.raise_for_status()
            
            tags = response.json()
            for tag in tags:
                if tag.get('name') == tag_name:
                    logger.debug(f"Found existing tag '{tag_name}' with ID {tag['id']}")
                    return tag['id']
            
            # Tag doesn't exist, create it
            response = self.session.post(url, json={"name": tag_name})
            response.raise_for_status()
            
            new_tag = response.json()
            logger.debug(f"Created tag '{tag_name}' with ID {new_tag.get('id')}")
            return new_tag['id']
            
        except requests.RequestException as e:
            logger.error(f"Failed to get or create tag '{tag_name}': {e}")
            raise
    
    def tag_assets(self, tag_id: str, asset_ids: List[str]) -> None:
        """
        Add tag to multiple assets
        
        Args:
            tag_id: Tag ID
            asset_ids: List of asset IDs to tag
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/tags/{tag_id}/assets"
        
        try:
            response = self.session.put(url, json={"ids": asset_ids})
            response.raise_for_status()
            
            logger.debug(f"Tagged {len(asset_ids)} assets with tag ID {tag_id}")
            
        except requests.RequestException as e:
            logger.error(f"Failed to tag assets: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test connection to Immich API
        
        Returns:
            True if connection successful, False otherwise
        """
        url = f"{self.base_url}/server/ping"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            logger.info("Successfully connected to Immich API")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to connect to Immich API: {e}")
            return False
