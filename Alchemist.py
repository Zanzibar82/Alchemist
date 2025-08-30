import re
import time
from tkinter import ttk
import threading
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import sys
from PIL import Image, ImageTk
import cv2
import numpy as np
from pathlib import Path

# Try to import drag-and-drop, fail gracefully
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("tkinterdnd2 not installed. Drag-and-drop feature won't be available.")

def resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Paths to FFmpeg binaries (essential for the GIF/MP4 conversions)
FFMPEG_PATH = resource_path("ffmpeg/bin/ffmpeg.exe")
FFPROBE_PATH = resource_path("ffmpeg/bin/ffprobe.exe")

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Alchemist - Media Converter")
        self.root.geometry("900x600")

        # Initialize state variables
        self.file_list = []
        self.output_folder = ""
        self.skip_h265_warning = None
        self.overwrite_all = None
        self.paused = False
        self.stopped = False
        self.conversion_thread = None

        # Create main frame
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left frame for buttons
        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Right frame for file list and log
        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Define conversion commands (GIF/MP4 use FFmpeg, WebP uses internal method)
        self.commands = [
            ("WebP → MP4", self.convert_webp_to_mp4_command),
            ("WebP → GIF", self.convert_webp_to_gif_command),
            ("MP4 → GIF", self.convert_mp4_to_gif_command),
            ("GIF → MP4", self.convert_gif_to_mp4_command),
            ("MKV → MP4 (PS3)", self.convert_mkv_to_mp4_command),
            ("Extract Audio", self.extract_audio_command),
            ("Any Audio → MP3 320k", self.convert_audio_to_mp3_command),
        ]

        # Create conversion buttons
        for label, command in self.commands:
            btn = tk.Button(self.left_frame, text=label, width=25, command=command)
            btn.pack(pady=3)

        # Add utility buttons
        tk.Button(self.left_frame, text="Add Files", command=self.add_files_dialog).pack(pady=5, fill=tk.X)
        tk.Button(self.left_frame, text="Remove Selected", command=self.remove_selected).pack(pady=2, fill=tk.X)
        tk.Button(self.left_frame, text="Clear List", command=self.clear_list).pack(pady=2, fill=tk.X)
        tk.Button(self.left_frame, text="Select Output", command=self.select_output_folder).pack(pady=5, fill=tk.X)
        
        # Add this in your __init__ method after creating the buttons
        tagline = tk.Label(self.left_frame, text="Manage and Transform Your Media", font=("Arial", 8), fg="gray")
        tagline.pack(pady=5)

        # File listbox
        self.listbox = tk.Listbox(self.right_frame, selectmode="extended")
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Configure drag and drop
        if HAS_DND:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self.on_drop)

        # Bind keyboard shortcuts
        self.listbox.bind("<Delete>", lambda event: self.remove_selected())
        self.listbox.bind("<Control-a>", self.select_all)

        # Output folder selection
        self.output_frame = tk.Frame(self.right_frame)
        self.output_frame.pack(fill=tk.X, pady=5)
        
        self.output_path_var = tk.StringVar(value="No output folder selected")
        tk.Label(self.output_frame, text="Output Folder:").pack(side=tk.LEFT)
        tk.Entry(self.output_frame, textvariable=self.output_path_var, state='readonly').pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Progress bar
        self.progress_frame = tk.Frame(self.right_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)
        
        self.status_label = tk.Label(self.progress_frame, text="Ready")
        self.status_label.pack()

        # Control buttons frame
        self.control_frame = tk.Frame(self.right_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        
        self.pause_btn = tk.Button(self.control_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = tk.Button(self.control_frame, text="Stop", command=self.stop_conversion, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Log text area
        self.log_text = scrolledtext.ScrolledText(self.right_frame, height=12, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def on_drop(self, event):
        """Handle file drop event"""
        if event.data:
            files = self.parse_dropped_files(event.data)
            self.add_files(files)

    def parse_dropped_files(self, data):
        """Parse dropped files from drag-and-drop event"""
        files = []
        if isinstance(data, str):
            # Handle Windows format with curly braces
            clean_data = data.strip('{}')
            potential_files = clean_data.split('} {')
            for file_path in potential_files:
                file_path = file_path.replace('{', '').replace('}', '').strip()
                if file_path and os.path.exists(file_path):
                    files.append(file_path)
        elif isinstance(data, list):
            files = data
        return files

    def add_files_dialog(self):
        """Open file dialog to add files"""
        files = filedialog.askopenfilenames(
            filetypes=[("All supported files", "*.webp *.gif *.mp4 *.mkv *.webm"), 
                      ("WebP files", "*.webp"),
                      ("GIF files", "*.gif"),
                      ("MP4 files", "*.mp4"),
                      ("MKV files", "*.mkv")]
        )
        self.add_files(files)

    def add_files(self, files):
        """Add files to the conversion list"""
        if isinstance(files, str):
            files = [files]
        
        for file in files:
            if file and os.path.isfile(file) and file not in self.file_list:
                self.file_list.append(file)
                self.listbox.insert(tk.END, os.path.basename(file))

    def remove_selected(self):
        """Remove selected files from the list"""
        selected_indices = self.listbox.curselection()
        for index in reversed(selected_indices):
            self.listbox.delete(index)
            self.file_list.pop(index)

    def clear_list(self):
        """Clear all files from the list"""
        self.listbox.delete(0, tk.END)
        self.file_list.clear()

    def select_all(self, event=None):
        """Select all files in the list"""
        self.listbox.select_set(0, tk.END)
        return "break"

    def select_output_folder(self):
        """Select output folder for converted files"""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_path_var.set(folder)

    def log_message(self, message):
        """Add message to log with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
        self.root.update_idletasks()

    def toggle_pause(self):
        """Toggle pause state during conversion"""
        self.paused = not self.paused
        self.pause_btn.config(text="Resume" if self.paused else "Pause")
        self.log_message("Conversion paused" if self.paused else "Conversion resumed")

    def stop_conversion(self):
        """Stop the conversion process"""
        self.stopped = True
        self.log_message("Stopping conversion...")

    def webp_to_mp4(self, input_path, output_path):
        """Convert WebP to MP4 using PIL and OpenCV (from script 1)"""
        try:
            webp = Image.open(input_path)
            width, height = webp.size

            # Check if it's animated
            if not getattr(webp, 'is_animated', False):
                self.log_message(f"{os.path.basename(input_path)} is not animated. Skipping.")
                return False

            total_duration_ms = 0
            frame_count = webp.n_frames

            # Calculate total duration and average FPS
            for i in range(frame_count):
                webp.seek(i)
                total_duration_ms += webp.info.get('duration', 100)

            average_fps = frame_count / (total_duration_ms / 1000.0)
            clamped_fps = max(5, min(60, average_fps))
            self.log_message(f"Calculated FPS: {average_fps:.2f}, Using: {clamped_fps:.2f}")

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, clamped_fps, (width, height))

            # Write each frame
            try:
                for frame_index in range(frame_count):
                    if self.stopped:
                        break
                    while self.paused:
                        time.sleep(0.1)
                        if self.stopped:
                            break
                    
                    webp.seek(frame_index)
                    frame_cv = cv2.cvtColor(np.array(webp.convert('RGB')), cv2.COLOR_RGB2BGR)
                    out.write(frame_cv)
            finally:
                out.release()

            self.log_message(f"Successfully wrote {frame_count} frames at {clamped_fps:.2f} FPS.")
            return True
            
        except Exception as e:
            self.log_message(f"Error converting {os.path.basename(input_path)}: {str(e)}")
            return False

    def webp_to_gif(self, input_path, output_path):
        """Convert animated WebP to animated GIF with perfect transparency handling and high quality"""
        try:
            with Image.open(input_path) as webp:
                # Check if it's animated
                if not getattr(webp, 'is_animated', False):
                    self.log_message(f"{os.path.basename(input_path)} is not animated. Skipping.")
                    return False

                frames = []
                frame_durations = []
                
                # First, check if the WebP has any transparency at all
                has_alpha = False
                test_frame = webp.convert('RGBA')
                if test_frame.mode == 'RGBA':
                    # Check if any pixel has transparency (alpha < 255)
                    alpha = test_frame.getchannel('A')
                    if alpha.getextrema()[0] < 255:
                        has_alpha = True
                
                # Process all frames
                for frame_index in range(webp.n_frames):
                    if self.stopped:
                        break
                    while self.paused:
                        time.sleep(0.1)
                        if self.stopped:
                            break

                    webp.seek(frame_index)
                    frame = webp.convert('RGBA')
                    
                    if has_alpha:
                        # PROPER transparency handling: composite onto white background
                        # This preserves semi-transparent pixels by blending them properly
                        background = Image.new('RGB', frame.size, (255, 255, 255))
                        
                        # Split the image into RGB and Alpha components
                        r, g, b, a = frame.split()
                        
                        # Composite the RGB image onto white background using the alpha channel as mask
                        # This is the CRITICAL FIX: use the alpha channel properly
                        background.paste(frame, (0, 0), a)  # Use alpha as mask
                        frame = background
                    else:
                        # No transparency, just convert to RGB
                        frame = frame.convert('RGB')
                    
                    # Convert to palette mode with high quality settings
                    # Use Image.ADAPTIVE for better color preservation
                    frame = frame.convert('P', palette=Image.ADAPTIVE, colors=256, dither=Image.NONE)
                    
                    frames.append(frame)
                    frame_durations.append(webp.info.get('duration', 100))

                if self.stopped:
                    return False

                if frames:
                    # Save as high quality animated GIF
                    frames[0].save(
                        output_path,
                        format='GIF',
                        save_all=True,
                        append_images=frames[1:],
                        duration=frame_durations,
                        loop=0,
                        disposal=2,  # Restore to background color between frames
                        optimize=True
                    )
                    
                    self.log_message(f"Successfully converted {webp.n_frames} frames to high-quality GIF.")
                    return True
                return False

        except Exception as e:
            self.log_message(f"Error converting {os.path.basename(input_path)} to GIF: {str(e)}")
            return False

    def convert_webp_to_gif_command(self):
        """Handle WebP to GIF conversion using our internal method"""
        if not self.validate_prerequisites():
            return

        self.stopped = False
        self.paused = False
        self.conversion_thread = threading.Thread(target=self.process_webp_to_gif_conversions, daemon=True)
        self.conversion_thread.start()

    def process_webp_to_gif_conversions(self):
        """Process all WebP files in the list for GIF conversion"""
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)

        total_files = len(self.file_list)
        successful = 0

        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break

                while self.paused:
                    time.sleep(0.1)
                    if self.stopped:
                        break

                # Only process WebP files for this command
                if not input_path.lower().endswith('.webp'):
                    continue

                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")

                # Create output path
                output_file = os.path.join(
                    self.output_folder,
                    os.path.splitext(os.path.basename(input_path))[0] + ".gif"
                )

                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue

                # Convert file
                if self.webp_to_gif(input_path, output_file):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)} to GIF")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)} to GIF")

        finally:
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.progress_var.set(100)

            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"GIF Conversion {status.lower()}. {successful}/{total_files} files converted.")

    def run_ffmpeg_command(self, command, input_path):
        """Run FFmpeg command with error handling"""
        try:
            self.log_message(f"Executing: {command}")
            result = subprocess.run(command, shell=True, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return True
        except subprocess.CalledProcessError as e:
            self.log_message(f"FFmpeg error for {os.path.basename(input_path)}: {e.stderr}")
            return False

    def convert_audio_to_mp3_command(self):
        """Handle audio to MP3 conversion using FFmpeg"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return
        
        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_audio_to_mp3_conversions,
            daemon=True
        )
        self.conversion_thread.start()

    def process_audio_to_mp3_conversions(self):
        """Process all audio files in the list for MP3 conversion"""
        total_files = len(self.file_list)
        successful = 0
        
        # Common audio file extensions
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.aiff', '.alac'}
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                # Get file extension and skip non-audio files
                file_ext = os.path.splitext(input_path)[1].lower()
                if file_ext not in audio_extensions:
                    continue
                
                # Skip if already MP3 (optional - you might want to re-encode anyway)
                if file_ext == '.mp3':
                    self.log_message(f"Skipping {os.path.basename(input_path)} (already MP3)")
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                
                # Create output path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + ".mp3")
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Build and run the MP3 conversion command
                command = f'"{FFMPEG_PATH}" -y -i "{input_path}" -c:a libmp3lame -b:a 320k -map_metadata 0 -id3v2_version 3 "{output_file}"'
                
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)} to MP3")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)} to MP3")
        
        finally:
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"Audio to MP3 conversion {status.lower()}. {successful}/{total_files} files converted.")

    def convert_webp_to_mp4_command(self):
        """Handle WebP to MP4 conversion using our internal method"""
        if not self.validate_prerequisites():
            return
        
        self.stopped = False
        self.paused = False
        self.conversion_thread = threading.Thread(target=self.process_webp_conversions, daemon=True)
        self.conversion_thread.start()

    def process_webp_conversions(self):
        """Process all WebP files in the list"""
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        
        total_files = len(self.file_list)
        successful = 0
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                while self.paused:
                    time.sleep(0.1)
                    if self.stopped:
                        break
                
                if not input_path.lower().endswith('.webp'):
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                
                # Create output path
                output_file = os.path.join(
                    self.output_folder,
                    os.path.splitext(os.path.basename(input_path))[0] + ".mp4"
                )
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Convert file
                if self.webp_to_mp4(input_path, output_file):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)}")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)}")
        
        finally:
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.progress_var.set(100)
            
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"Conversion {status.lower()}. {successful}/{total_files} files converted.")

    def convert_mp4_to_gif_command(self):
        """Convert MP4 to GIF using FFmpeg"""
        self.run_ffmpeg_conversion(
            'ffmpeg -i "{input}" -vf "fps=30,scale=480:-1:flags=lanczos" "{output}"',
            ".mp4",
            ".gif"
        )

    def convert_gif_to_mp4_command(self):
        """Convert GIF to MP4 using FFmpeg"""
        self.run_ffmpeg_conversion(
            'ffmpeg -i "{input}" -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -pix_fmt yuv420p -c:v libx264 -movflags faststart "{output}"',
            ".gif",
            ".mp4"
        )

    def convert_mkv_to_mp4_command(self):
        """Convert MKV to MP4 with smart PS3 compatibility checking"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return
        
        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_mkv_to_mp4_ps3_compatible,
            daemon=True
        )
        self.conversion_thread.start()

    def process_mkv_to_mp4_ps3_compatible(self):
        """Process MKV files with PS3 compatibility checks"""
        total_files = len(self.file_list)
        successful = 0
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                # Only process MKV files
                if not input_path.lower().endswith('.mkv'):
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Analyzing: {os.path.basename(input_path)}")
                
                # Create output path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + ".mp4")
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Analyze the source file to determine the best approach
                needs_reencoding = self.needs_ps3_reencoding(input_path)
                
                if needs_reencoding:
                    # Source is not PS3 compatible, need to re-encode
                    self.status_label.config(text=f"Converting (re-encoding): {os.path.basename(input_path)}")
                    command = f'"{FFMPEG_PATH}" -i "{input_path}" -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 192k -y "{output_file}"'
                else:
                    # Source is already PS3 compatible, just remux
                    self.status_label.config(text=f"Converting (copying): {os.path.basename(input_path)}")
                    command = f'"{FFMPEG_PATH}" -i "{input_path}" -c copy -movflags +faststart -y "{output_file}"'
                
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    mode = "re-encoded" if needs_reencoding else "copied"
                    self.log_message(f"Successfully {mode} {os.path.basename(input_path)} for PS3 compatibility")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)}")
        
        finally:
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"MKV to MP4 (PS3) conversion {status.lower()}. {successful}/{total_files} files converted.")

    def needs_ps3_reencoding(self, input_path):
        """Check if a video file needs re-encoding for PS3 compatibility"""
        try:
            # Check video codec
            video_check = [
                FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,pix_fmt', '-of', 'default=noprint_wrappers=1:nokey=1',
                input_path
            ]
            
            result = subprocess.run(video_check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, check=True, timeout=30)
            
            lines = result.stdout.strip().split('\n')
            codec_name = lines[0] if len(lines) > 0 else ''
            pix_fmt = lines[1] if len(lines) > 1 else ''
            
            # PS3 requires H.264 video with yuv420p pixel format
            if codec_name != 'h264' or pix_fmt != 'yuv420p':
                self.log_message(f"Source needs re-encoding: codec={codec_name}, pixel_format={pix_fmt}")
                return True
            
            # Check audio codec (PS3 works best with AAC audio)
            audio_check = [
                FFPROBE_PATH, '-v', 'error', '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1',
                input_path
            ]
            
            result = subprocess.run(audio_check, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, check=True, timeout=30)
            
            audio_codec = result.stdout.strip()
            
            # If audio is not AAC, we should re-encode
            if audio_codec not in ['aac', 'mp3']:
                self.log_message(f"Audio needs re-encoding: {audio_codec}")
                return True
            
            return False
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self.log_message(f"Error analyzing {os.path.basename(input_path)}: {e}")
            # If we can't analyze, assume re-encoding is needed for safety
            return True

    def extract_audio_command(self):
        """Extract audio from video files"""
        self.run_ffmpeg_conversion(
            'ffmpeg -i "{input}" -vn -acodec copy "{output}"',
            "",  # Any video file
            ".m4a"
        )

    def run_ffmpeg_conversion(self, command_template, input_ext, output_ext):
        """Generic method to run FFmpeg conversions"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return
        
        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_ffmpeg_conversions, 
            args=(command_template, input_ext, output_ext),
            daemon=True
        )
        self.conversion_thread.start()

    def process_ffmpeg_conversions(self, command_template, input_ext, output_ext):
        """Process files using FFmpeg"""
        total_files = len(self.file_list)
        successful = 0
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                # Skip files that don't match the input extension
                if input_ext and not input_path.lower().endswith(input_ext):
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                
                # Create output path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + output_ext)
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Build and run command
                command = command_template.format(input=input_path, output=output_file)
                command = command.replace("ffmpeg", f'"{FFMPEG_PATH}"', 1)
                
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)}")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)}")
        
        finally:
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"Conversion {status.lower()}. {successful}/{total_files} files converted.")

    def validate_prerequisites(self):
        """Check if we have files and output folder selected"""
        if not self.file_list:
            messagebox.showwarning("Warning", "No files selected!")
            return False
        
        if not self.output_folder:
            messagebox.showwarning("Warning", "No output folder selected!")
            return False
        
        return True

    def has_ffmpeg(self):
        """Check if FFmpeg is available"""
        if not os.path.exists(FFMPEG_PATH):
            messagebox.showerror("Error", f"FFmpeg not found at: {FFMPEG_PATH}\nPlease ensure FFmpeg is in the correct location.")
            return False
        return True

    def ask_overwrite(self, filename):
        """Ask user if they want to overwrite an existing file"""
        result = messagebox.askyesno(
            "File Exists", 
            f"The file '{filename}' already exists. Do you want to overwrite it?"
        )
        return result

if __name__ == "__main__":
    # Create root window with drag-and-drop support if available
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = VideoConverterApp(root)
    root.mainloop()
