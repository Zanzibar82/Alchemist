# Alchemist - Universal Media Converter

**Alchemist** is a powerful, user-friendly desktop application built to simplify media conversion. It transforms a complex process into a simple drag-and-drop experience, supporting a wide range of popular formats.

Turn animated WebPs into MP4s or GIFs, convert between video formats, extract audio, and ensure perfect compatibility for old DVD players, CRTs, and devices like PlayStation 3 — all without ever touching a command line.

## Features

**Alchemist provides a potent mix of conversion powers:**

- Versatile Conversions:
    - WebP to MP4: Perfectly converts animated WebPs to high-quality MP4 videos
    - WebP to GIF: Creates smooth, high-quality GIFs from animated WebPs with proper transparency handling
    - MP4 to GIF: Convert video to animated GIF
    - GIF to MP4: Convert animated GIF to video
    - MP4 to WebM: Convert to modern web format using VP9/Opus codecs
    - WebM to MP4: Convert WebM to widely compatible MP4
    - MKV to MP4 (PS3 Compatible): Smart conversion that ensures perfect playback on PlayStation 3
    - Video to XviD AVI: Convert any video to XviD AVI format for old DVD players and CRT TVs
    - Audio Extraction: Pull audio tracks directly from video files
    - Any Audio to MP3: Convert any audio file (FLAC, M4A, WAV, etc.) to high-quality 320kbps MP3

- Smart & Powerful:
    - XviD Quality Presets: Three quality levels for old device compatibility:
        - Low (1500k): Fast encoding, optimized for USB 1.1 flash drives
        - Optimal (2000k): Balanced speed and quality for daily use
        - High (3000k): Maximum quality, best for DVD burning
    - PS3-Optimized: Automatically uses the correct H.264 yuv420p video and AAC audio settings for guaranteed console compatibility
    - CRT/DVD Player Optimized: Proper scaling with lanczos algorithm, correct 23.976fps framerate preservation, and XviD Simple Profile for maximum hardware compatibility
    - Smart Encoding: Analyzes source files to avoid unnecessary re-encoding, saving time and preserving quality
    - High-Quality Output: Uses intelligent defaults (like CRF 23 and adaptive palettes) for the best balance of size and quality

- User-Friendly GUI:
    - Drag & Drop: Simply drag files onto the window to add them to the queue
    - Batch Processing: Convert multiple files at once
    - Progress Tracking: Monitor conversions with a real-time progress bar and detailed log
    - Pause/Stop: Full control over long conversion tasks
    - Audio Track Selection: Choose from multiple audio tracks in MKV files
    - Automatic Audio Delay Detection: Handles out-of-sync audio from MKV containers

## Installation & Usage

### Prerequisites

- Windows operating system (7, 8, 10, or 11)
- Python 3.6 or higher
- FFmpeg (included with the application or downloaded separately)

### Quick Start

1. Download or Clone the Repository

2. Install Python Dependencies

pip install -r requirements.txt

3. Obtain FFmpeg

The application requires FFmpeg binaries. You have two options:

Option A: Use the included get_ffmpeg.py script

python get_ffmpeg.py

This will automatically download and extract FFmpeg to the correct location.

Option B: Manual installation
- Download FFmpeg from the official website
- Extract the contents
- Place the ffmpeg.exe and ffprobe.exe in ffmpeg/bin/ folder relative to the application

4. Run the Application

python Alchemist.py

### Folder Structure
Alchemist/
├── Alchemist.py # Main application
├── get_ffmpeg.py # FFmpeg download helper
├── ffmpeg/ # FFmpeg binaries folder
│ └── bin/
│ ├── ffmpeg.exe
│ ├── ffprobe.exe
│ └── ... (other DLLs)
├── requirements.txt # Python dependencies
└── README.md # This file


### How to Use

1. Select Output Folder: Click "Select Output" to choose where converted files will be saved
2. Add Files: Drag and drop files onto the window or click "Add Files"
3. Choose Conversion: Click one of the conversion buttons (e.g., "Video to XviD AVI")
4. For XviD Conversion: Select quality preset based on your playback device:
   - Low (1500k): Best for USB flash drives on old DVD players
   - Optimal (2000k): Balanced quality and file size
   - High (3000k): Maximum quality for DVD burning
5. Monitor Progress: Watch the progress bar and log for real-time updates

### Supported Input Formats

- Video: MP4, MKV, AVI, MOV, WMV, FLV, TS, M4V, MPG, MPEG, WebM
- Image/Animation: WebP, GIF
- Audio: WAV, FLAC, AAC, MP3, OGG, WMA, M4A, AIFF, AC3

### Output Formats

- MP4 (H.264/AAC)
- WebM (VP9/Opus)
- GIF
- XviD AVI (MPEG-4 ASP/MP3)
- MP3 (320kbps)

## Troubleshooting

FFmpeg not found error
- Ensure FFmpeg is properly installed in ffmpeg/bin/ folder
- Run get_ffmpeg.py to automatically download the correct binaries

XviD conversion stutters on USB
- Use the "Low" quality preset (1500k) for USB flash drives
- Burn to DVD-R instead for smoother playback of high-bitrate files
- Most old DVD players have USB 1.1 ports that struggle above 1800k

Audio out of sync
- The application automatically detects and corrects audio delays from MKV files
- For other containers, ensure you're selecting the correct audio track

Conversion is slow
- Use "Low" or "Optimal" quality presets for faster encoding
- High preset uses rate-distortion optimization which takes 2-3x longer

## Notes

- The XviD encoder produces files compatible with most DVD players from the mid-2000s onward
- For CRT TVs, the 720px width with lanczos scaling provides optimal picture quality
- When burning to DVD, always finalize the disc and use DVD-R media for best compatibility
- USB 1.1 ports on old DVD players typically max out at 1500-1800 kbps for reliable playback

## License

Distributed under the MIT License.

Note: This project distributes binaries of FFmpeg, which is licensed under the LGPLv2.1/GPLv2.
The relevant license texts are provided in the LICENSES directory. The source code for FFmpeg
is available from the official FFmpeg website.
