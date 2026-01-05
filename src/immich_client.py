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
    
    def search_album_assets_without_tag(self, album_id: str, exclude_tag_id: str) -> List[Dict[str, Any]]:
        """
        Search for assets in an album that don't have any tags (tagIds: null)
        
        Args:
            album_id: Album UUID
            exclude_tag_id: Not used anymore, kept for compatibility
            
        Returns:
            List of asset dictionaries that are in the album and have no tags
            
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
    
    def get_album_assets(self, album_id: str) -> List[Dict[str, Any]]:
        """
        Get all assets from an album
        
        Args:
            album_id: Album UUID
            
        Returns:
            List of asset dictionaries
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/albums/{album_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            album_data = response.json()
            assets = album_data.get("assets", [])
            
            logger.debug(f"Retrieved {len(assets)} assets from album {album_id}")
            return assets
            
        except requests.RequestException as e:
            logger.error(f"Failed to get album assets: {e}")
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
    
    def create_tag(self, tag_name: str) -> Dict[str, Any]:
        """
        Create a new tag in Immich
        
        Args:
            tag_name: Name of the tag to create
            
        Returns:
            Tag object with id
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/tags"
        
        try:
            response = self.session.post(url, json={"name": tag_name})
            response.raise_for_status()
            
            tag = response.json()
            logger.debug(f"Created tag '{tag_name}' with ID {tag.get('id')}")
            return tag
            
        except requests.RequestException as e:
            logger.error(f"Failed to create tag '{tag_name}': {e}")
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
        # Try to get all tags and find matching name
        url = f"{self.base_url}/tags"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            tags = response.json()
            for tag in tags:
                if tag.get('name') == tag_name:
                    logger.debug(f"Found existing tag '{tag_name}' with ID {tag['id']}")
                    return tag['id']
            
            # Tag doesn't exist, create it
            tag = self.create_tag(tag_name)
            return tag['id']
            
        except requests.RequestException as e:
            logger.error(f"Failed to get or create tag '{tag_name}': {e}")
            raise
    
    def get_asset_tags(self, asset_id: str) -> List[str]:
        """
        Get all tags for a specific asset
        
        Args:
            asset_id: Asset UUID
            
        Returns:
            List of tag names
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/assets/{asset_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            asset_data = response.json()
            tags = asset_data.get('tags', [])
            tag_names = [tag.get('name') for tag in tags if tag.get('name')]
            
            logger.debug(f"Asset {asset_id} has tags: {tag_names}")
            return tag_names
            
        except requests.RequestException as e:
            logger.error(f"Failed to get tags for asset {asset_id}: {e}")
            raise
    
    def asset_has_tag(self, asset_id: str, tag_name: str) -> bool:
        """
        Check if an asset has a specific tag
        
        Args:
            asset_id: Asset UUID
            tag_name: Tag name to check for
            
        Returns:
            True if asset has the tag, False otherwise
        """
        try:
            tags = self.get_asset_tags(asset_id)
            return tag_name in tags
        except Exception as e:
            logger.warning(f"Could not check tags for asset {asset_id}, assuming not tagged: {e}")
            return False
    
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
