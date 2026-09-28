from app.core.config import settings

def s3_client():
    if not all([settings.S3_ENDPOINT, settings.S3_BUCKET, settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY]):
        return None
    import boto3
    return boto3.client('s3', endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)

def presign_put(key: str, content_type: str = 'image/jpeg', expires: int = 900):
    c = s3_client()
    if not c: return None
    return c.generate_presigned_url('put_object', Params={'Bucket': settings.S3_BUCKET, 'Key': key, 'ContentType': content_type}, ExpiresIn=expires)

def presign_get(key: str, expires: int = 300):
    c = s3_client()
    if not c: return None
    return c.generate_presigned_url('get_object', Params={'Bucket': settings.S3_BUCKET, 'Key': key}, ExpiresIn=expires)

def put_bytes(key: str, data: bytes, content_type: str = 'application/pdf') -> bool:
    c = s3_client()
    if not c: return False
    c.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return True

def public_url(key: str):
    return f'{settings.S3_PUBLIC_BASE_URL.rstrip("/")}/{key}' if settings.S3_PUBLIC_BASE_URL else key
