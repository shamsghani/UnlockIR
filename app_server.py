"""
SPECTRA // IR-CORE - Windows Hello Infrared Camera Studio
---------------------------------------------------------
Precision Infrared Camera Suite with Cyber-Tactical Awwwards UI,
Interactive Sliders, Live Telemetry Terminal, and Virtual Camera Bridge.
"""

import argparse
import asyncio
import io
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

import winsdk.windows.graphics.imaging as wgi
import winsdk.windows.media.capture as wmc
import winsdk.windows.media.capture.frames as wmcf
import winsdk.windows.storage.streams as streams

try:
    import pyvirtualcam
    HAS_PYVIRTUALCAM = True
except ImportError:
    HAS_PYVIRTUALCAM = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(BASE_DIR, "Captures")
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Redirect stdout / stderr when launched via pythonw.exe (no console)
if sys.stdout is None or sys.stderr is None:
    try:
        log_f = open(os.path.join(BASE_DIR, "app.log"), "a", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = log_f
        if sys.stderr is None:
            sys.stderr = log_f
    except Exception:
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")

# ---------------------------------------------------------
# Global State & Settings
# ---------------------------------------------------------
class CameraState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        
        # Camera session
        self.mc = None
        self.reader = None
        self.w = 640
        self.h = 360
        self.fps_target = 30
        self.actual_fps = 0.0
        self.frame_count = 0
        self.latest_jpeg = None
        self.latest_raw_frame = None
        self.latest_processed_bgr = None
        
        # Telemetry
        self.min_val = 0
        self.max_val = 0
        self.mean_val = 0.0
        self.histogram = [0] * 16
        self.illum_status = "ACTIVE"
        self.vcam_active = False
        self.vcam_device = None
        
        # Logs (circular buffer for Side Terminal)
        self.logs = deque(maxlen=150)
        
        # Tunable Settings (Sliders)
        self.exposure_ev = 0.0       # -3.0 to +3.0
        self.gain = 1.0              # 1.0 to 10.0x
        self.gamma = 1.0             # 0.4 to 2.5
        self.brightness = 0          # -100 to +100
        self.contrast = 1.0          # 0.5 to 3.0x
        
        # CLAHE
        self.clahe_enabled = True
        self.clahe_clip = 3.5        # 1.0 to 10.0
        self.clahe_grid = 8          # 4 to 16
        
        # Colormap preset: 'mono', 'inferno', 'phosphor', 'cyan', 'magma', 'turbo', 'bone'
        self.colormap = 'phosphor'
        
        # Auto-Reignite Automation
        self.auto_reignite = False
        self.last_reignite_time = time.time()
        self.auto_reignite_interval = 60 # seconds

    def log(self, category, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {
            "time": timestamp,
            "category": category,
            "message": message,
            "level": level
        }
        with self.lock:
            self.logs.append(entry)
        print(f"[{timestamp}] [{category}] {message}")

state = CameraState()

# ---------------------------------------------------------
# Image Processing Pipeline
# ---------------------------------------------------------
def build_gamma_table(gamma):
    inv_gamma = 1.0 / max(0.1, gamma)
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
    return table

def process_frame(raw_img):
    with state.lock:
        exp_ev = state.exposure_ev
        gain = state.gain
        gamma_val = state.gamma
        bright = state.brightness
        cont = state.contrast
        clahe_on = state.clahe_enabled
        clip = state.clahe_clip
        grid = max(2, int(state.clahe_grid))
        cmap = state.colormap

    # 1. Exposure / Gain scaling
    mult = gain * (2.0 ** exp_ev)
    if mult != 1.0 or bright != 0 or cont != 1.0:
        scaled = cv2.convertScaleAbs(raw_img, alpha=mult * cont, beta=bright)
    else:
        scaled = raw_img.copy()

    # 2. Gamma Correction
    if abs(gamma_val - 1.0) > 0.05:
        lut = build_gamma_table(gamma_val)
        scaled = cv2.LUT(scaled, lut)

    # 3. CLAHE (Adaptive Histogram Equalization)
    if clahe_on:
        try:
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
            enhanced = clahe.apply(scaled)
        except Exception:
            enhanced = scaled
    else:
        enhanced = scaled

    # 4. Color Mapping
    if cmap == 'inferno':
        bgr = cv2.applyColorMap(enhanced, cv2.COLORMAP_INFERNO)
    elif cmap == 'magma':
        bgr = cv2.applyColorMap(enhanced, cv2.COLORMAP_MAGMA)
    elif cmap == 'turbo':
        bgr = cv2.applyColorMap(enhanced, cv2.COLORMAP_TURBO)
    elif cmap == 'bone':
        bgr = cv2.applyColorMap(enhanced, cv2.COLORMAP_BONE)
    elif cmap == 'phosphor':
        # Tactical Military NVG P43 Green Phosphor (B: 15%, G: 100%, R: 25%)
        b = (enhanced * 0.15).astype(np.uint8)
        g = enhanced
        r = (enhanced * 0.25).astype(np.uint8)
        bgr = cv2.merge([b, g, r])
    elif cmap == 'cyan':
        # Cyber Tactical Ice Blue (B: 100%, G: 90%, R: 10%)
        b = enhanced
        g = (enhanced * 0.90).astype(np.uint8)
        r = (enhanced * 0.10).astype(np.uint8)
        bgr = cv2.merge([b, g, r])
    else:  # 'mono'
        bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    return bgr

# ---------------------------------------------------------
# WinRT Camera Worker Loop
# ---------------------------------------------------------
class CameraWorker:
    def __init__(self):
        self.vcam = None
        self.reignite_event = threading.Event()

    async def init_session(self):
        state.log("SENSOR", "Enumerating MediaFrameSourceGroups...")
        groups = await wmcf.MediaFrameSourceGroup.find_all_async()
        ir_group = None
        for group in groups:
            for src in group.source_infos:
                if src.source_kind == wmcf.MediaFrameSourceKind.INFRARED:
                    ir_group = group
                    break
            if ir_group:
                break

        if not ir_group:
            state.log("SENSOR", "Windows Hello IR camera not detected!", "ERROR")
            return False

        state.log("SENSOR", f"Binding to IR Group: {ir_group.display_name}")
        settings = wmc.MediaCaptureInitializationSettings()
        settings.source_group = ir_group
        settings.streaming_capture_mode = wmc.StreamingCaptureMode.VIDEO
        settings.memory_preference = wmc.MediaCaptureMemoryPreference.CPU
        settings.sharing_mode = wmc.MediaCaptureSharingMode.SHARED_READ_ONLY

        state.mc = wmc.MediaCapture()
        try:
            await state.mc.initialize_async(settings)
        except Exception:
            settings.sharing_mode = wmc.MediaCaptureSharingMode.EXCLUSIVE_CONTROL
            await state.mc.initialize_async(settings)

        ir_source = None
        for _, src in state.mc.frame_sources.items():
            if src.info.source_kind == wmcf.MediaFrameSourceKind.INFRARED:
                ir_source = src
                break

        try:
            formats = list(ir_source.supported_formats)
            if formats:
                pref = next((f for f in formats if f.frame_rate.numerator == 30), formats[0])
                await ir_source.set_format_async(pref)
        except Exception:
            pass

        cf = ir_source.current_format
        state.w = cf.video_format.width if cf and cf.video_format else 640
        state.h = cf.video_format.height if cf and cf.video_format else 360
        state.fps_target = cf.frame_rate.numerator if cf and cf.frame_rate else 30

        state.reader = await state.mc.create_frame_reader_async(ir_source)
        status = await state.reader.start_async()
        if status != wmcf.MediaFrameReaderStartStatus.SUCCESS:
            state.log("SENSOR", f"Failed to start FrameReader (status={status})", "ERROR")
            return False

        state.log("SENSOR", f"Stream engaged: {state.w}x{state.h} @ {state.fps_target} FPS (L8)", "SUCCESS")
        return True

    async def close_session(self):
        if state.reader:
            try:
                await state.reader.stop_async()
            except Exception:
                pass
            state.reader = None
        if state.mc:
            try:
                state.mc.close()
            except Exception:
                pass
            state.mc = None

    async def run_loop(self):
        if not await self.init_session():
            return

        buf_len = state.w * state.h
        buf = streams.Buffer(buf_len)
        raw_bytes = bytearray(buf_len)

        fps_counter = 0
        fps_start = time.time()

        while state.running:
            # Check for Re-ignite request
            if self.reignite_event.is_set():
                self.reignite_event.clear()
                state.log("ILLUM", "Hardware reset requested. Re-igniting IR emitter...")
                await self.close_session()
                await asyncio.sleep(0.3)
                await self.init_session()
                state.last_reignite_time = time.time()
                state.log("ILLUM", "Session reset complete. Watchdog timer refreshed.", "SUCCESS")
                continue

            # Auto-reignite check
            if state.auto_reignite and (time.time() - state.last_reignite_time > state.auto_reignite_interval):
                self.reignite_event.set()

            frame = state.reader.try_acquire_latest_frame()
            if frame and frame.video_media_frame and frame.video_media_frame.software_bitmap:
                sb = frame.video_media_frame.software_bitmap
                converted = wgi.SoftwareBitmap.convert(sb, wgi.BitmapPixelFormat.GRAY8)
                converted.copy_to_buffer(buf)

                dr = streams.DataReader.from_buffer(buf)
                dr.read_bytes(raw_bytes)
                raw_img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((state.h, state.w))

                # Telemetry stats
                mean_l = float(raw_img.mean())
                min_l = int(raw_img.min())
                max_l = int(raw_img.max())
                
                # 16-bin histogram
                hist, _ = np.histogram(raw_img, bins=16, range=(0, 256))
                norm_hist = [int((h / hist.max()) * 100) if hist.max() > 0 else 0 for h in hist]

                # Process frame
                bgr_img = process_frame(raw_img)

                # JPEG encode for HTTP MJPEG stream
                ret, jpeg = cv2.imencode('.jpg', bgr_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # Virtual Camera broadcast
                if state.vcam_active:
                    if self.vcam is None and HAS_PYVIRTUALCAM:
                        try:
                            self.vcam = pyvirtualcam.Camera(width=state.w, height=state.h, fps=state.fps_target, fmt=pyvirtualcam.PixelFormat.BGR)
                            state.vcam_device = self.vcam.device
                            state.log("VCAM", f"Broadcasting live to '{self.vcam.device}'", "SUCCESS")
                        except Exception as e:
                            state.vcam_active = False
                            state.log("VCAM", f"Virtual Camera failed: {e}", "ERROR")
                    if self.vcam:
                        self.vcam.send(bgr_img)
                        self.vcam.sleep_until_next_frame()
                else:
                    if self.vcam:
                        self.vcam.close()
                        self.vcam = None
                        state.log("VCAM", "Virtual Camera broadcast disabled.")

                # Update global state
                with state.lock:
                    state.latest_raw_frame = raw_img
                    state.latest_processed_bgr = bgr_img
                    if ret:
                        state.latest_jpeg = jpeg.tobytes()
                    state.mean_val = mean_l
                    state.min_val = min_l
                    state.max_val = max_l
                    state.histogram = norm_hist
                    state.illum_status = "ACTIVE" if mean_l > 1.5 else "STANDBY / PASSIVE"
                    state.frame_count += 1

                fps_counter += 1
                now = time.time()
                if now - fps_start >= 1.0:
                    state.actual_fps = fps_counter / (now - fps_start)
                    fps_counter = 0
                    fps_start = now

            await asyncio.sleep(0.005)

        await self.close_session()
        if self.vcam:
            self.vcam.close()

camera_worker = CameraWorker()

def start_camera_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(camera_worker.run_loop())

# ---------------------------------------------------------
# HTTP & REST API Server
# ---------------------------------------------------------
class StudioHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in terminal
        pass

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "index.html missing")

        elif path == "/stream.mjpeg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()

            try:
                while state.running:
                    with state.lock:
                        jpeg_bytes = state.latest_jpeg
                    if jpeg_bytes:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode("utf-8"))
                        self.wfile.write(jpeg_bytes)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.033)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass

        elif path == "/api/telemetry":
            with state.lock:
                # Get snapshots list
                snaps = []
                if os.path.exists(CAPTURES_DIR):
                    for fn in sorted(os.listdir(CAPTURES_DIR), reverse=True)[:6]:
                        if fn.endswith(".png"):
                            snaps.append(fn)

                data = {
                    "fps": round(state.actual_fps, 1),
                    "mean": round(state.mean_val, 2),
                    "min": state.min_val,
                    "max": state.max_val,
                    "histogram": state.histogram,
                    "illum_status": state.illum_status,
                    "vcam_active": state.vcam_active,
                    "vcam_device": state.vcam_device or "OBS Virtual Camera",
                    "frame_count": state.frame_count,
                    "logs": list(state.logs)[-25:],
                    "snapshots": snaps,
                    "settings": {
                        "exposure_ev": state.exposure_ev,
                        "gain": state.gain,
                        "gamma": state.gamma,
                        "brightness": state.brightness,
                        "contrast": state.contrast,
                        "clahe_enabled": state.clahe_enabled,
                        "clahe_clip": state.clahe_clip,
                        "clahe_grid": state.clahe_grid,
                        "colormap": state.colormap,
                        "auto_reignite": state.auto_reignite
                    }
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path.startswith("/captures/"):
            filename = os.path.basename(path)
            file_path = os.path.join(CAPTURES_DIR, filename)
            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        payload = json.loads(body) if body else {}

        if path == "/api/settings":
            with state.lock:
                for k, v in payload.items():
                    if hasattr(state, k):
                        setattr(state, k, v)
            state.log("SETTINGS", f"Updated: {list(payload.keys())}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif path == "/api/reignite":
            camera_worker.reignite_event.set()
            state.log("USER", "Triggered manual IR Illuminator re-ignite.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"reigniting"}')

        elif path == "/api/snapshot":
            with state.lock:
                img = state.latest_processed_bgr
            if img is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"IR_Capture_{ts}.png"
                out_path = os.path.join(CAPTURES_DIR, fn)
                cv2.imwrite(out_path, img)
                state.log("CAPTURE", f"Saved snapshot: {fn}", "SUCCESS")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "saved", "filename": fn}).encode("utf-8"))
            else:
                self.send_error(500, "No frame available")

        elif path == "/api/vcam/toggle":
            with state.lock:
                state.vcam_active = not state.vcam_active
                status = "ENABLED" if state.vcam_active else "DISABLED"
            state.log("VCAM", f"User toggled Virtual Camera: {status}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"vcam_active": state.vcam_active}).encode("utf-8"))

        elif path == "/api/open_folder":
            try:
                os.startfile(CAPTURES_DIR)
            except Exception:
                subprocess.Popen(f'explorer "{os.path.normpath(CAPTURES_DIR)}"')
            state.log("USER", "Opened captures directory in File Explorer.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"opened"}')
        else:
            self.send_error(404, "Not Found")

# ---------------------------------------------------------
# Launch Application Window & Server
# ---------------------------------------------------------
def find_app_browser():
    """Locate an installed Chromium-based browser supporting --app mode for a borderless native app frame."""
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData", "")

    candidates = [
        # Microsoft Edge (64-bit, 32-bit, user local)
        os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(local_app_data, "Microsoft", "Edge", "Application", "msedge.exe") if local_app_data else None,
        # Google Chrome
        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe") if local_app_data else None,
        # Brave Browser
        os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(program_files_x86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None

def main():
    parser = argparse.ArgumentParser(description="SPECTRA // IR-CORE - Precision Infrared Studio Suite")
    parser.add_argument("--port", type=int, default=8765, help="HTTP server port (default: 8765)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="HTTP server host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Start server without automatically opening browser")
    args = parser.parse_args()

    print("==========================================================")
    print("  SPECTRA // IR-CORE - Infrared Studio Suite")
    print("==========================================================")
    state.log("SYSTEM", "Initializing Spectra IR Studio engine...")

    # Start camera worker thread
    cam_thread = threading.Thread(target=start_camera_thread, daemon=True)
    cam_thread.start()

    # Start HTTP server
    server = ThreadingHTTPServer((args.host, args.port), StudioHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    app_url = f"http://{args.host}:{args.port}"
    state.log("HTTP", f"Studio interface online at {app_url}")

    if not args.no_browser:
        app_browser = find_app_browser()
        temp_profile = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "spectra_ir_profile")

        if app_browser:
            browser_name = os.path.basename(app_browser)
            state.log("UI", f"Launching native application frame via {browser_name}...")
            cmd = [
                app_browser,
                f"--app={app_url}",
                "--window-size=1420,880",
                f"--user-data-dir={temp_profile}",
                "--enable-features=OverlayScrollbar"
            ]
            browser_proc = subprocess.Popen(cmd)
            try:
                browser_proc.wait()
            except KeyboardInterrupt:
                pass
        else:
            state.log("UI", f"Opening {app_url} in default web browser...")
            try:
                webbrowser.open(app_url)
            except Exception:
                pass
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        state.log("UI", f"Headless server running at {app_url}. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    state.running = False
    server.shutdown()
    state.log("SYSTEM", "Studio session closed cleanly.")

if __name__ == "__main__":
    main()
