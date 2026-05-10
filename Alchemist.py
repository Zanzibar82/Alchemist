import re
import time
from tkinter import ttk
import threading
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import argparse
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
            ("WebM → MP4", self.convert_webm_to_mp4_command),
            ("WebP → MP4", self.convert_webp_to_mp4_command),
            ("WebP → GIF", self.convert_webp_to_gif_command),
            ("MP4 → WebM", self.convert_mp4_to_webm_command),
            ("MP4 → GIF", self.convert_mp4_to_gif_command),
            ("GIF → MP4", self.convert_gif_to_mp4_command),
            ("MKV → MP4 (PS3)", self.convert_mkv_to_mp4_command),
            ("Extract Audio", self.extract_audio_command),
            ("Any Audio → MP3 320k", self.convert_audio_to_mp3_command),
            ("Any Video → XviD AVI", self.convert_to_old_device_command),
        ]

        # Create conversion buttons
        for label, command in self.commands:
            btn = tk.Button(self.left_frame, text=label, width=25, command=command)
            btn.pack(pady=3)

        # Add spacer to push utility buttons down
        spacer = tk.Frame(self.left_frame, height=50)  # Adjust height as needed
        spacer.pack(fill=tk.X, pady=10)

        # Create a dedicated frame for utility buttons
        self.utility_frame = tk.Frame(self.left_frame)
        self.utility_frame.pack(fill=tk.X, pady=5)


        # Add utility buttons
        tk.Button(self.left_frame, text="Select Output...", command=self.select_output_folder).pack(pady=5, fill=tk.X)
        tk.Button(self.left_frame, text="Add Files...", command=self.add_files_dialog).pack(pady=5, fill=tk.X)
        tk.Button(self.left_frame, text="Remove Selected", command=self.remove_selected).pack(pady=2, fill=tk.X)
        tk.Button(self.left_frame, text="Clear List", command=self.clear_list).pack(pady=2, fill=tk.X)
       
        # Tagline
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
                      ("MKV files", "*.mkv"),
                      ("WebM files", "*.webm")]
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
        
    def convert_to_old_device_command(self):
        """Convert any video to XviD AVI for old CRT/DVD player compatibility"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return

        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        # Collect audio selections on the main thread BEFORE starting conversion
        audio_selections = {}
        for input_path in self.file_list:
            file_ext = os.path.splitext(input_path)[1].lower()
            if file_ext not in video_extensions:
                continue
            audio_selections[input_path] = self.ask_audio_track(input_path)

        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_to_old_device_conversions,
            args=(audio_selections,),
            daemon=True
        )
        self.conversion_thread.start()

    def process_to_old_device_conversions(self, audio_selections):
        """Process all video files for old device compatibility"""
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)

        total_files = len(self.file_list)
        successful = 0
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break

                while self.paused:
                    time.sleep(0.1)
                    if self.stopped:
                        break

                file_ext = os.path.splitext(input_path)[1].lower()
                if file_ext not in video_extensions:
                    continue

                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                self.root.update_idletasks()  # Force UI update

                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + "_vintage.avi")

                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue

                audio_index = audio_selections.get(input_path, 0)
                self.log_message(f"Selected audio track index: {audio_index}")

                # Get audio delay for the selected track
                audio_delay_ms = self.get_audio_delay(input_path, audio_index)
                
                if audio_delay_ms != 0:
                    delay_seconds = audio_delay_ms / 1000.0
                    self.log_message(f"Applying audio delay of {delay_seconds:.3f} seconds using adelay")
                    # Fixed command with -shortest in correct position
                    command = (
                        f'"{FFMPEG_PATH}" -i "{input_path}" '
                        f'-map 0:v:0 -map 0:a:{audio_index} -sn '
                        f'-vf "scale=720:-2,fps=25,setsar=1" '
                        f'-c:v libxvid -vtag XVID -b:v 900k -bf 2 -trellis 1 -threads 0 '
                        f'-af "adelay={audio_delay_ms}|{audio_delay_ms}" '
                        f'-c:a libmp3lame -b:a 128k -ar 48000 -ac 2 '
                        f'-shortest '
                        f'-y "{output_file}"'
                    )
                else:
                    command = (
                        f'"{FFMPEG_PATH}" -i "{input_path}" '
                        f'-map 0:v:0 -map 0:a:{audio_index} -sn '
                        f'-vf "scale=720:-2,fps=25,setsar=1" '
                        f'-c:v libxvid -vtag XVID -b:v 900k -bf 2 -trellis 1 -threads 0 '
                        f'-c:a libmp3lame -b:a 128k -ar 48000 -ac 2 '
                        f'-y "{output_file}"'
                    )

                if self.run_ffmpeg_command(command, input_path):
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
            self.log_message(f"Old Device conversion {status.lower()}. {successful}/{total_files} files converted.")

    def convert_webm_to_mp4_command(self):
        """Handle WebM to MP4 conversion"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return
        
        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_webm_to_mp4_conversions,
            daemon=True
        )
        self.conversion_thread.start()

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
        """Run FFmpeg command with error handling and progress output"""
        try:
            self.log_message(f"Executing: {command}")
            # Use Popen to capture stderr in real-time
            process = subprocess.Popen(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            # Read stderr for progress info
            for line in process.stderr:
                if 'time=' in line:
                    # Extract time info for progress feedback
                    import re
                    time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                    if time_match:
                        self.log_message(f"Progress: {time_match.group(1)}")
                # Also check for errors
                if 'error' in line.lower():
                    self.log_message(f"FFmpeg: {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                return True
            else:
                self.log_message(f"FFmpeg error for {os.path.basename(input_path)}: return code {process.returncode}")
                return False
                
        except Exception as e:
            self.log_message(f"FFmpeg error for {os.path.basename(input_path)}: {str(e)}")
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
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.aiff', '.alac', '.ac3'}
        
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

    def convert_mp4_to_webm_command(self):
        """Convert MP4 to WebM using FFmpeg"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return
        
        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_mp4_to_webm_conversions,
            daemon=True
        )
        self.conversion_thread.start()
        
    def process_mp4_to_webm_conversions(self):
        """Process all MP4 files in the list for WebM conversion"""
        total_files = len(self.file_list)
        successful = 0
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                # Only process MP4 files
                if not input_path.lower().endswith('.mp4'):
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                
                # Create output path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + ".webm")
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Build FFmpeg command for MP4 to WebM conversion
                # VP9 codec gives better quality but is slower
                # VP8 is faster but lower quality
                command = f'"{FFMPEG_PATH}" -i "{input_path}" -c:v libvpx-vp9 -crf 30 -b:v 0 -c:a libopus -b:a 128k -y "{output_file}"'
                
                # Alternative using VP8 (faster, lower quality):
                # command = f'"{FFMPEG_PATH}" -i "{input_path}" -c:v libvpx -crf 10 -b:v 1M -c:a libvorbis -y "{output_file}"'
                
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)} to WebM")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)} to WebM")
        
        finally:
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"MP4 to WebM conversion {status.lower()}. {successful}/{total_files} files converted.")        

    def convert_mkv_to_mp4_command(self):
        """Convert any video to MP4 with PS3 compatibility"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return

        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        # Collect audio selections on main thread before starting conversion
        audio_selections = {}
        for input_path in self.file_list:
            file_ext = os.path.splitext(input_path)[1].lower()
            if file_ext not in video_extensions:
                continue
            audio_selections[input_path] = self.ask_audio_track(input_path)

        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_mkv_to_mp4_ps3_compatible,
            args=(audio_selections,),
            daemon=True
        )
        self.conversion_thread.start()

    def process_webm_to_mp4_conversions(self):
        """Process all WebM files in the list for MP4 conversion"""
        total_files = len(self.file_list)
        successful = 0
        
        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break
                
                # Only process WebM files for this command
                if not input_path.lower().endswith('.webm'):
                    continue
                
                # Update progress
                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                
                # Create output path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + ".mp4")
                
                # Check if output file exists
                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue
                
                # Build FFmpeg command for WebM to MP4 conversion
                command = f'"{FFMPEG_PATH}" -i "{input_path}" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k -movflags +faststart -pix_fmt yuv420p -y "{output_file}"'
                
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    self.log_message(f"Successfully converted {os.path.basename(input_path)} to MP4")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)} to MP4")
        
        finally:
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"WebM to MP4 conversion {status.lower()}. {successful}/{total_files} files converted.")

    def process_mkv_to_mp4_ps3_compatible(self, audio_selections):
        """Process video files for PS3 compatibility"""
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)

        total_files = len(self.file_list)
        successful = 0
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break

                while self.paused:
                    time.sleep(0.1)
                    if self.stopped:
                        break

                file_ext = os.path.splitext(input_path)[1].lower()
                if file_ext not in video_extensions:
                    continue

                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Analyzing: {os.path.basename(input_path)}")

                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_file = os.path.join(self.output_folder, base_name + "_ps3.mp4")

                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        continue

                audio_index = audio_selections.get(input_path, 0)
                self.log_message(f"Selected audio track index: {audio_index}")

                # Analyze video stream
                needs_video_reencode, reason = self.needs_ps3_video_reencode(input_path)
                self.log_message(f"Video re-encode needed: {needs_video_reencode} ({reason})")

                if needs_video_reencode:
                    video_args = (
                        f'-c:v libx264 -preset medium -crf 23 '
                        f'-profile:v high -level:v 4.1 '
                        f'-pix_fmt yuv420p -movflags +faststart'
                    )
                else:
                    video_args = '-c:v copy'

                # Audio always re-encoded to AAC for PS3 safety
                audio_args = f'-c:a aac -b:a 192k -ar 48000 -ac 2'

                command = (
                    f'"{FFMPEG_PATH}" -i "{input_path}" '
                    f'-map 0:v:0 -map 0:a:{audio_index} -sn '
                    f'{video_args} {audio_args} '
                    f'-y "{output_file}"'
                )

                self.status_label.config(text=f"Converting: {os.path.basename(input_path)}")
                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    mode = "re-encoded" if needs_video_reencode else "remuxed"
                    self.log_message(f"Successfully {mode} {os.path.basename(input_path)} for PS3")
                else:
                    self.log_message(f"Failed to convert {os.path.basename(input_path)}")

        finally:
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully converted {successful}/{total_files} files.")
            self.log_message(f"PS3 conversion {status.lower()}. {successful}/{total_files} files converted.")

    def needs_ps3_video_reencode(self, input_path):
        """Check if video stream needs re-encoding for PS3. Returns (bool, reason)."""
        try:
            result = subprocess.run(
                [FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=codec_name,pix_fmt,profile,level,width,height',
                 '-of', 'json', input_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )

            import json
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if not streams:
                return True, "no video stream found"

            s = streams[0]
            codec = s.get('codec_name', '')
            pix_fmt = s.get('pix_fmt', '')
            profile = s.get('profile', '').lower()
            level = int(s.get('level', 999))
            width = int(s.get('width', 0))
            height = int(s.get('height', 0))

            if codec != 'h264':
                return True, f"codec is {codec}, not h264"
            if pix_fmt != 'yuv420p':
                return True, f"pixel format is {pix_fmt}"
            if 'high' not in profile and 'main' not in profile and 'baseline' not in profile:
                return True, f"unsupported profile: {profile}"
            if level > 41:
                return True, f"level {level} exceeds PS3 max (41)"
            if width > 1920 or height > 1080:
                return True, f"resolution {width}x{height} exceeds 1080p"

            return False, "already PS3 compatible"

        except Exception as e:
            return True, f"analysis error: {e}"

    def extract_audio_command(self):
        """Extract audio from video files with track selection"""
        if not self.validate_prerequisites():
            return
        if not self.has_ffmpeg():
            return

        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        # Collect audio selections on main thread before starting
        audio_selections = {}
        for input_path in self.file_list:
            file_ext = os.path.splitext(input_path)[1].lower()
            if file_ext not in video_extensions:
                continue
            audio_selections[input_path] = self.ask_audio_track(input_path)

        self.stopped = False
        self.conversion_thread = threading.Thread(
            target=self.process_extract_audio,
            args=(audio_selections,),
            daemon=True
        )
        self.conversion_thread.start()
        
    def process_extract_audio(self, audio_selections):
        """Extract selected audio track from video files"""
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)

        total_files = len(self.file_list)
        successful = 0
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m4v', '.mpg', '.mpeg'}

        try:
            for i, input_path in enumerate(self.file_list):
                if self.stopped:
                    break

                while self.paused:
                    time.sleep(0.1)
                    if self.stopped:
                        break

                file_ext = os.path.splitext(input_path)[1].lower()
                self.log_message(f"Processing: {os.path.basename(input_path)} (ext: {file_ext})")
                
                if file_ext not in video_extensions:
                    self.log_message(f"Skipping: extension {file_ext} not in video_extensions list")
                    continue

                progress = (i / total_files) * 100
                self.progress_var.set(progress)
                self.status_label.config(text=f"Extracting: {os.path.basename(input_path)}")

                base_name = os.path.splitext(os.path.basename(input_path))[0]
                
                audio_index = audio_selections.get(input_path, 0)
                self.log_message(f"Audio index selected: {audio_index}")
                
                ext = self.get_audio_extension(input_path, audio_index)
                self.log_message(f"Detected audio extension: {ext}")
                
                output_file = os.path.join(self.output_folder, base_name + ext)
                self.log_message(f"Output file will be: {output_file}")

                if os.path.exists(output_file):
                    if not self.ask_overwrite(os.path.basename(output_file)):
                        self.log_message(f"Skipped (user declined overwrite): {output_file}")
                        continue

                command = (
                    f'"{FFMPEG_PATH}" -i "{input_path}" '
                    f'-map 0:a:{audio_index} '
                    f'-vn -acodec copy '
                    f'-y "{output_file}"'
                )
                self.log_message(f"Running command: {command}")

                if self.run_ffmpeg_command(command, input_path):
                    successful += 1
                    self.log_message(f"Successfully extracted audio from {os.path.basename(input_path)}")
                else:
                    self.log_message(f"FAILED to extract audio from {os.path.basename(input_path)}")

        finally:
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.progress_var.set(100)
            status = "Stopped" if self.stopped else "Completed"
            self.status_label.config(text=f"{status}! Successfully extracted {successful}/{total_files} files.")
            self.log_message(f"Audio extraction {status.lower()}. {successful}/{total_files} files extracted.")

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

    def ask_audio_track(self, input_path):
        """Show a dialog to select audio track. Returns track index or 0 if only one/cancelled."""
        try:
            result = subprocess.run(
                [FFPROBE_PATH, '-v', 'error', '-select_streams', 'a',
                 '-show_entries', 'stream=index,codec_name,channels,bit_rate:stream_tags=language,title',
                 '-of', 'json', input_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )

            import json
            data = json.loads(result.stdout)
            streams = data.get('streams', [])

            # Only one or no tracks — return default
            if len(streams) <= 1:
                return 0

            # Build label for each track
            track_labels = []
            for i, s in enumerate(streams):
                tags = s.get('tags', {})
                lang = tags.get('language', 'unknown')
                title = tags.get('title', '')
                codec = s.get('codec_name', '?')
                channels = s.get('channels', '?')
                bitrate = s.get('bit_rate', '')
                bitrate_str = f", {int(bitrate)//1000}k" if str(bitrate).isdigit() else ''
                label = f"Track {i+1}: [{lang}] {codec} {channels}ch{bitrate_str}"
                if title:
                    label += f" — {title}"
                track_labels.append(label)

            # Show dialog on main thread (we're already on main thread here)
            selected_index = [0]

            dialog = tk.Toplevel(self.root)
            dialog.title("Select Audio Track")
            dialog.geometry("500x300")
            dialog.grab_set()
            dialog.resizable(False, False)
            dialog.focus_force()

            tk.Label(dialog, text=f"Multiple audio tracks found in:\n{os.path.basename(input_path)}",
                     wraplength=460, justify='left').pack(pady=(15, 5), padx=15)

            listbox = tk.Listbox(dialog, selectmode='single', height=len(track_labels))
            for label in track_labels:
                listbox.insert(tk.END, label)
            listbox.select_set(0)
            listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

            def confirm():
                sel = listbox.curselection()
                selected_index[0] = sel[0] if sel else 0
                dialog.destroy()

            def on_close():
                selected_index[0] = 0
                dialog.destroy()

            dialog.protocol("WM_DELETE_WINDOW", on_close)
            tk.Button(dialog, text="Use Selected Track", command=confirm, width=20).pack(pady=10)

            dialog.wait_window()  # Blocks until dialog is closed, safe on main thread
            return selected_index[0]

        except Exception as e:
            self.log_message(f"Error reading audio tracks: {e}")
            return 0

    def get_audio_extension(self, input_path, audio_index):
        """Return the appropriate file extension for the selected audio track."""
        try:
            import json
            result = subprocess.run(
                [FFPROBE_PATH, '-v', 'error', '-select_streams', f'a:{audio_index}',
                 '-show_entries', 'stream=codec_name',
                 '-of', 'json', input_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if not streams:
                return '.m4a'
            
            codec = streams[0].get('codec_name', '').lower()
            
            extension_map = {
                'aac':    '.aac',
                'mp3':    '.mp3',
                'ac3':    '.ac3',
                'eac3':   '.eac3',
                'dts':    '.dts',
                'flac':   '.flac',
                'opus':   '.opus',
                'vorbis': '.ogg',
                'pcm_s16le': '.wav',
                'pcm_s24le': '.wav',
                'pcm_f32le': '.wav',
                'truehd': '.thd',
            }
            
            return extension_map.get(codec, '.mka')  # fallback to .mka (Matroska audio) for unknown codecs
        
        except Exception as e:
            self.log_message(f"Warning: could not detect audio codec, defaulting to .m4a: {e}")
            return '.m4a'            

    def get_audio_delay(self, input_path, audio_index):
        """
        Extract audio delay by analyzing edit lists and packet timestamps.
        This works for MKV files with container-level audio delays.
        """
        try:
            # Get first few audio packets to find the actual PTS (presentation timestamp)
            result = subprocess.run(
                [FFPROBE_PATH, '-v', 'error', '-select_streams', f'a:{audio_index}',
                 '-show_entries', 'packet=pts,pts_time',
                 '-read_intervals', '%+#10',  # Read first 10 packets
                 '-of', 'json', input_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            
            import json
            data = json.loads(result.stdout)
            packets = data.get('packets', [])
            
            if packets:
                # Get the first packet's PTS (presentation timestamp)
                first_pts = float(packets[0].get('pts_time', 0))
                if first_pts > 0.1:  # Significant delay
                    delay_ms = int(first_pts * 1000)
                    self.log_message(f"Detected audio delay from packets: {delay_ms/1000:.3f}s")
                    return delay_ms
            
            # Fallback: Compare video and audio first packet timestamps
            video_packets = subprocess.run(
                [FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'packet=pts_time',
                 '-read_intervals', '%+#1',
                 '-of', 'json', input_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            
            video_data = json.loads(video_packets.stdout)
            video_pkts = video_data.get('packets', [])
            video_pts = float(video_pkts[0].get('pts_time', 0)) if video_pkts else 0
            
            audio_pkts = packets
            audio_pts = float(audio_pkts[0].get('pts_time', 0)) if audio_pkts else 0
            
            delay_ms = int((audio_pts - video_pts) * 1000)
            
            if abs(delay_ms) > 10:
                self.log_message(f"Detected audio delay from packet comparison: {delay_ms/1000:.3f}s")
                return delay_ms
                
            return 0
            
        except Exception as e:
            self.log_message(f"Warning: Could not extract audio delay: {e}")
            return 0
            
if __name__ == "__main__":
    # Create root window with drag-and-drop support if available
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = VideoConverterApp(root)
    root.mainloop()
