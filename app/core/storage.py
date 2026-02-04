from minio import Minio
from .config import settings

minio_client = Minio(endpoint=settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=False)


def create_minio_bucket_if_not_exists():
    buckets = [settings.MINIO_BUCKET_NAME, "audio-files", "cover-art"]

    for bucket_name in buckets:
        try:
            found = minio_client.bucket_exists(bucket_name)
            if not found:
                minio_client.make_bucket(bucket_name)
                print(f"Bucket '{bucket_name}' created.")
            else:
                print(f"Bucket '{bucket_name}' already exists.")
        except Exception as e:
            print(f"Error connecting to MinIO for bucket '{bucket_name}': {e}")
