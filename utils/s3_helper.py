def upload_file_to_s3(file_obj, folder='', filename='file.png'):
    import boto3, os
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )
    
    # Gunakan filename yang diberikan
    key = f"{folder}/{filename}" if folder else filename
    
    s3_client.upload_fileobj(
        file_obj,
        os.getenv("S3_BUCKET_NAME"),
        key,
        ExtraArgs={"ContentType": "image/png"}
    )
    
    bucket_name = os.getenv("S3_BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    return f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"

def delete_file_from_s3(s3_url):
    """
    Menghapus file di S3 berdasarkan URL.
    Contoh URL: https://bucket-name.s3.region.amazonaws.com/folder/filename.png
    """
    import boto3, os
    from urllib.parse import urlparse

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )

    parsed = urlparse(s3_url)
    bucket = os.getenv("S3_BUCKET_NAME")  # bisa juga diambil dari parsed.netloc
    key = parsed.path.lstrip('/')

    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        print(f"Gagal hapus file S3: {e}")
        return False
