# apps/common/s3_utils.py
import boto3
import uuid
from urllib.parse import urlparse
from django.conf import settings

_s3_client = None


def get_s3_client():
    """Use explicit keys if provided, otherwise rely on Lambda IAM role credentials."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    kwargs = {"region_name": settings.AWS_S3_REGION_NAME}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs.update(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def upload_file_to_s3(file, folder):

    file_extension = file.name.split(".")[-1]
    file_name = f"{folder}/{uuid.uuid4()}.{file_extension}"

    get_s3_client().upload_fileobj(
        file,
        settings.AWS_STORAGE_BUCKET_NAME,
        file_name,
        ExtraArgs={"ContentType": file.content_type}
    )

    return f"{settings.AWS_S3_BASE_URL}/{file_name}"


def delete_file_from_s3(file_url):
    """
    Delete file from S3 using URL
    """

    if not file_url:
        return

    parsed = urlparse(file_url)
    key = parsed.path.lstrip("/")

    get_s3_client().delete_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key
    )



