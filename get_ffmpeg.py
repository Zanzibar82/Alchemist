import requests
import zipfile
import os
import shutil
from pathlib import Path

def download_ffmpeg():
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg_temp.zip"
    extract_dir = "ffmpeg_temp"
    output_dir = "ffmpeg"
    output_bin_dir = os.path.join(output_dir, "bin")

    # Clean up any previous attempts
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    # Create necessary directories
    Path(extract_dir).mkdir(exist_ok=True)
    Path(output_bin_dir).mkdir(parents=True, exist_ok=True)

    try:
        print("Downloading FFmpeg from gyan.dev...")
        # Stream the download to handle large files
        with requests.get(ffmpeg_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        print("Extracting FFmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract everything first to temp directory
            zip_ref.extractall(extract_dir)
        
        # Find the extracted ffmpeg folder
        extracted_folders = [f for f in os.listdir(extract_dir) if f.startswith('ffmpeg-') and os.path.isdir(os.path.join(extract_dir, f))]
        if not extracted_folders:
            raise Exception("Could not find ffmpeg folder in the downloaded zip")
        
        ffmpeg_folder_name = extracted_folders[0]
        source_bin_dir = os.path.join(extract_dir, ffmpeg_folder_name, 'bin')
        
        if not os.path.exists(source_bin_dir):
            raise Exception("Could not find 'bin' directory in the extracted files")
        
        # Copy all files from the temp bin to the final bin directory
        for file_name in os.listdir(source_bin_dir):
            source_file = os.path.join(source_bin_dir, file_name)
            dest_file = os.path.join(output_bin_dir, file_name)
            if os.path.isfile(source_file):
                shutil.copy2(source_file, dest_file)
        
        print("FFmpeg downloaded and installed successfully!")
        print(f"Binaries placed in: {output_bin_dir}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please manually download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/")
        
    finally:
        # Clean up temporary files
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        if os.path.exists(zip_path):
            os.remove(zip_path)

if __name__ == "__main__":
    download_ffmpeg()
