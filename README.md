# Alchemist - Universal Media Converter

![Python](https://img.shields.io/badge/Python-3.6%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

**Alchemist** is a powerful, user-friendly desktop application built to simplify media conversion. It transforms a complex process into a simple drag-and-drop experience, supporting a wide range of popular formats.

Turn animated WebPs into MP4s or GIFs, convert between video formats, extract audio, and ensure perfect compatibility for devices like PlayStation 3 — all without ever touching a command line.

![Alchemist GUI](https://raw.githubusercontent.com/Zanzibar82/Alchemist/refs/heads/main/Alchemist.png)

## ✨ Features

**Alchemist provides a potent mix of conversion powers:**

*   **🔄 Versatile Conversions:**
    *   **WebP → MP4:** Perfectly converts animated WebPs to high-quality MP4 videos.
    *   **WebP → GIF:** Creates smooth, high-quality GIFs from animated WebPs with proper transparency handling.
    *   **MP4 ↔ GIF:** Seamlessly convert between video and GIF formats.
    *   **MKV → MP4 (PS3 Compatible):** Smart conversion that ensures perfect playback on PlayStation 3 and other legacy devices.
    *   **Audio Extraction:** Pull audio tracks directly from video files.
    *   **Any Audio → MP3:** Convert any audio file (FLAC, M4A, WAV, etc.) to high-quality 320kbps MP3.

*   **🎯 Smart & Powerful:**
    *   **PS3-Optimized:** Automatically uses the correct H.264 `yuv420p` video and AAC audio settings for guaranteed console compatibility.
    *   **Smart Encoding:** Analyzes source files to avoid unnecessary re-encoding, saving time and preserving quality.
    *   **High-Quality Output:** Uses intelligent defaults (like CRF 23 and adaptive palettes) for the best balance of size and quality.

*   **💻 User-Friendly GUI:**
    *   **Drag & Drop:** Simply drag files onto the window to add them to the queue.
    *   **Batch Processing:** Convert multiple files at once.
    *   **Progress Tracking:** Monitor conversions with a real-time progress bar and detailed log.
    *   **Pause/Stop:** Full control over long conversion tasks.

## 🚀 Installation & Usage

### Prerequisites
*   **Python 3.6 or higher**
*   **FFmpeg** (for GIF/MP4/MKV/Audio conversions). The app looks for it in an `ffmpeg/bin/` folder.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

Make sure folder structure is as follows:
```bash
Alchemist/
├── Alchemist.py
├── get_ffmpeg.py
├── ffmpeg/
│ └── bin/
│ ├── ffmpeg.exe
│ ├── ffprobe.exe
│ ├── avcodec-60.dll
│ └── ... (all other DLLs)
├── requirements.txt
└── README.md
```

## 📜 License ----------------

Distributed under the MIT License. See `LICENSE` for more information.

**Note:** This project distributes binaries of FFmpeg, which is licensed under the LGPLv2.1/GPLv2. The relevant license texts are provided in the `LICENSES` directory. The source code for FFmpeg is available from the [official FFmpeg website](https://ffmpeg.org/source.html).
