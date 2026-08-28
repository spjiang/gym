"""MinIO 对象存储：建桶、读写、匿名读公开图。"""

from __future__ import annotations

import io
import json

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

PUBLIC_BUCKET = "public"
PRIVATE_BUCKET = "private"

_PUBLIC_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{PUBLIC_BUCKET}/*"],
        }
    ],
}


def minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )


def ensure_buckets() -> None:
    """确保桶存在，并为 public 打开匿名 GET。"""
    client = minio_client()
    for bucket in (PUBLIC_BUCKET, PRIVATE_BUCKET):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    client.set_bucket_policy(PUBLIC_BUCKET, json.dumps(_PUBLIC_POLICY))


def put_bytes(bucket: str, name: str, data: bytes, content_type: str) -> None:
    minio_client().put_object(
        bucket,
        name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def object_exists(bucket: str, name: str) -> bool:
    try:
        minio_client().stat_object(bucket, name)
        return True
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
            return False
        raise


def get_bytes(bucket: str, name: str) -> bytes:
    response = minio_client().get_object(bucket, name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def remove_object(bucket: str, name: str) -> None:
    minio_client().remove_object(bucket, name)
