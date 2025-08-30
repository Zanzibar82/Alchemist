import requests
import zipfile
import os
from pathlib import Path

def download_ffmpeg():
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg.zip"
    extract_dir = "ffmpeg"

    # Create the ffmpeg directory if it doesn't exist
    Path(extract_dir).mkdir(exist_ok=True)

    print("Downloading FFmpeg...")
    # Stream the download to handle large files
    with requests.get(ffmpeg_url, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    print("Extracting FFmpeg...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Extract only the 'bin' folder from the archive
        for file in zip_ref.namelist():
            if file.startswith('ffmpeg-') and '/bin/' in file:
                zip_ref.extract(file, extract_dir)

    # Clean up the zip file
    os.remove(zip_path)
    print("FFmpeg downloaded and extracted successfully to the 'ffmpeg' folder.")

if __name__ == "__main__":
    download_ffmpeg()
