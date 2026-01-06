import sys
import os
import time

from PIL import Image
from loguru import logger
from tqdm import tqdm

from auraframes.api.accountApi import AccountApi
from auraframes.api.activityApi import ActivityApi
from auraframes.api.assetApi import AssetApi
from auraframes.api.frameApi import FrameApi
from auraframes.api.peopleApi import PeopleApi
from auraframes.aws.s3client import S3Client
from auraframes.aws.sqsclient import SQSClient
from auraframes.client import Client
from auraframes.exif import ExifWriter
from auraframes.export import get_image_from_asset
from auraframes.models.asset import Asset, AssetPartialId
from auraframes.utils.io import build_path, write_model


class Aura:

    def __init__(self):
        self._init_logger()
        self._client = Client()
        # TODO: Can probably use DI for passing around the client?
        self.account_api = AccountApi(self._client)
        self.frame_api = FrameApi(self._client)
        self.people_api = PeopleApi(self._client)
        self.activity_api = ActivityApi(self._client)
        self.asset_api = AssetApi(self._client)
        self.exif_writer = ExifWriter()

    def login(self, email: str = os.getenv('AURA_EMAIL'), password: str = os.getenv('AURA_PASSWORD')):
        """

        :param email: The email of the account to authenticate with, defaults to ENVIRON['AURA_EMAIL']
        :param password: The password of the account to authenticate with, defaults to ENVIRON['AURA_PASSWORD']
        :return: Authenticated Aura object
        """
        user = self.account_api.login(email, password)

        self._client.add_default_headers({
            'x-token-auth': user.auth_token,
            'x-user-id': user.id
        })

        return self

    def main(self):
        pass

    def get_all_assets(self, frame_id: str):
        paginated_assets, cursor = self.frame_api.get_assets(frame_id)
        assets = paginated_assets
        while cursor:
            paginated_assets, cursor = self.frame_api.get_assets(frame_id, cursor=cursor)
            time.sleep(1)  # TODO: Make better (tm)
            assets.extend(paginated_assets)

        return assets

    def dump_frame(self, frame_id: str, path: str, download_images: bool = True, download_activities: bool = True):
        frame, _ = self.frame_api.get_frame(frame_id)
        frame_dir = build_path(path, f'{frame.name}-{frame.id}/')

        write_model(frame, build_path(frame_dir, 'frame.json'))

        if download_activities:
            activities = self.frame_api.get_activities(frame.id)
            write_model(activities, build_path(frame_dir, 'activities.json'))

        assets = self.get_all_assets(frame_id)
        write_model(assets, build_path(frame_dir, 'assets.json'))

        if download_images:
            self.download_images_from_assets(assets, build_path(frame_dir, f'asset_images/'))

    def download_images_from_assets(self, assets: list[Asset], base_path: str):
        failed_to_retrieve = []
        for asset in tqdm(assets):
            try:
                get_image_from_asset(asset, base_path, self.exif_writer)
            except Exception as e:
                failed_to_retrieve.append(asset)
        if len(failed_to_retrieve) > 0:
            logger.debug(f'Failed to retrieve {len(failed_to_retrieve)} assets.')

    def clone(self, source_frame, target_frame):
        # TODO: Read assets from one frame and immediately clones them to another (in memory)
        pass

    def upload_images(self):
        # TODO: tqdm, for each asset, upload_image
        # TODO: How do we know where the original dumped asset images are?
        #       Could rebuild the file path or store it in assets.json
        pass

    def upload_image(self, frame_id: str, image_path: str, asset: Asset):
        try:
            image = Image.open(image_path)
        except Exception as e:
            logger.error(e)
            return
        local_identifier = asset.local_identifier
        self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
        queue_url = self.get_sqs()
        self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
        self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
        client = S3Client()
        filename, md5 = client.upload_file(
            open(image_path, 'rb').read(), '.jpg')

        asset.file_name = filename
        asset.md5_hash = md5
        asset.height = image.height
        asset.width = image.width

        self.asset_api.batch_update(asset)
        message = self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
        print(message)

    def upload_video(self, frame_id: str, video_path: str, poster_path: str, duration: float, asset: Asset):
        """
        Upload a video file to a frame.
        
        This method uploads both a poster frame (thumbnail) and the video file to S3,
        then updates the asset with video-specific metadata.
        
        :param frame_id: ID of the frame to upload to
        :param video_path: Path to the video file
        :param poster_path: Path to the poster/thumbnail JPEG image
        :param duration: Video duration in seconds
        :param asset: Asset object with metadata
        """
        try:
            poster_image = Image.open(poster_path)
        except Exception as e:
            logger.error(f"Failed to open poster image {poster_path}: {e}")
            return
        
        try:
            # Step 1: Select asset on frame
            local_identifier = asset.local_identifier
            self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
            
            # Step 2: Poll SQS
            queue_url = self.get_sqs()
            self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
            
            # Step 3: Select asset again
            self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
            
            # Step 4: Upload poster frame to S3
            s3_client = S3Client()
            poster_data = open(poster_path, 'rb').read()
            poster_filename, poster_md5 = s3_client.upload_file(poster_data, '.jpeg')
            logger.info(f"Uploaded poster: {poster_filename}")
            
            # Step 5: Upload video to S3
            video_data = open(video_path, 'rb').read()
            video_filename, video_md5 = s3_client.upload_file(video_data, '.mp4')
            logger.info(f"Uploaded video: {video_filename}")
            
            # Step 6: Update asset with video metadata
            asset.file_name = poster_filename
            asset.video_file_name = video_filename
            asset.md5_hash = poster_md5
            asset.height = poster_image.height
            asset.width = poster_image.width
            asset.duration = duration
            asset.duration_unclipped = duration
            asset.video_clip_start = 0
            asset.video_clip_excludes_audio = False
            asset.data_uti = "public.jpeg"  # For the poster
            asset.is_live = 1
            asset.ios_media_subtypes = 1048576  # Video media subtype
            
            # Step 7: Batch update asset
            self.asset_api.batch_update(asset)
            
            # Step 8: Poll SQS again
            message = self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
            logger.debug(f"SQS message: {message}")
            
            logger.info(f"Successfully uploaded video {video_path} to frame {frame_id}")
            
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            raise

    def get_sqs(self):
        self.sqsClient = SQSClient()
        # TODO: Is this a hardcoded queue URL?
        queueUrl = self.sqsClient.get_queue_url('4ab446b4-33a7-4a76-881d-d545d153ab5a')
        return queueUrl

    def _init_logger(self):
        # logger.remove()  # remove / set this to debug if needed
        logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                                                    "<level>{level: <8}</level> | "
                                                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                                                    "<level>{message}</level> Context: {extra}")
        logger.add('logs/file_{time}.log')
