import sys
import time
from loguru import logger

# Enable HEIC support if available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.debug("HEIC support enabled")
except ImportError:
    logger.warning("pillow-heif not installed, HEIC files may not work")

from config import Config
from sync_service import SyncService


def main():
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=Config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    try:
        # Load configuration
        Config.load()
        
        # Initialize service
        service = SyncService()
        
        # Test Immich connection
        if not service.immich.test_connection():
            logger.error("Failed to connect to Immich, exiting")
            sys.exit(1)
        
        logger.info(f"Starting sync service (interval: {Config.SYNC_INTERVAL_MINUTES} minutes)")
        
        # Main sync loop
        while True:
            try:
                logger.info("=" * 50)
                logger.info("Starting sync cycle")
                start_time = time.time()
                
                stats = service.sync_album()
                
                elapsed = time.time() - start_time
                logger.info(f"Sync cycle completed in {elapsed:.1f}s")
                logger.info(f"Stats: {stats}")
                
            except Exception as e:
                logger.error(f"Sync cycle failed: {e}", exc_info=True)
            
            # Wait for next sync
            sleep_seconds = Config.SYNC_INTERVAL_MINUTES * 60
            logger.info(f"Sleeping for {Config.SYNC_INTERVAL_MINUTES} minutes until next sync")
            time.sleep(sleep_seconds)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down gracefully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
