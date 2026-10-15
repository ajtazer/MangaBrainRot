#!/usr/bin/env python3
"""
Upload all downloaded music files to Cloudflare R2
"""

import os
import boto3
from botocore.config import Config
from pathlib import Path

# Cloudflare R2 configuration (same as manga-video-api)
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "3edc2a55a5af4b14b554c8ed89ceadb7")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "manga-videos")
R2_PUBLIC_URL = "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev"

# Folder paths
MUSIC_DIR = Path(__file__).parent / "music"
R2_BGM_FOLDER = "bgm"


def get_r2_client():
    if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        print("❌ R2 credentials not set!")
        print("Please set environment variables:")
        print("  export R2_ACCESS_KEY_ID='your_access_key'")
        print("  export R2_SECRET_ACCESS_KEY='your_secret_key'")
        return None
    
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )


def upload_file(client, file_path: Path, key: str) -> bool:
    """Upload a single file to R2"""
    try:
        client.upload_file(
            str(file_path),
            R2_BUCKET_NAME,
            key,
            ExtraArgs={'ContentType': 'audio/mpeg'}
        )
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("📤 R2 BGM Uploader")
    print("=" * 50)
    
    # Get R2 client
    client = get_r2_client()
    if not client:
        return
    
    # Get all MP3 files
    mp3_files = list(MUSIC_DIR.glob("*.mp3"))
    print(f"Found {len(mp3_files)} MP3 files to upload")
    print("=" * 50)
    
    success = 0
    failed = 0
    
    for i, mp3_file in enumerate(mp3_files, 1):
        filename = mp3_file.name
        key = f"{R2_BGM_FOLDER}/{filename}"
        
        print(f"\n[{i}/{len(mp3_files)}] Uploading: {filename}")
        
        if upload_file(client, mp3_file, key):
            url = f"{R2_PUBLIC_URL}/{key}".replace(" ", "%20")
            print(f"  ✅ Uploaded: {url}")
            success += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"✅ Success: {success}/{len(mp3_files)}")
    print(f"❌ Failed: {failed}/{len(mp3_files)}")
    
    # Print the n8n array
    print("\n" + "=" * 50)
    print("📋 Copy this to your n8n Extract Chapter ID node:\n")
    print("const allBgmTracks = [")
    for mp3_file in sorted(mp3_files):
        safe_filename = mp3_file.name.replace(" ", "%20")
        print(f'  "{R2_PUBLIC_URL}/{R2_BGM_FOLDER}/{safe_filename}",')
    print("];")


if __name__ == "__main__":
    main()
