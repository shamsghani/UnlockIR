"""
Windows Hello IR Camera -> System Virtual Webcam Bridge
-------------------------------------------------------
Pipes the laptop's Windows Hello IR camera stream into the system-wide
OBS Virtual Camera device so it can be selected as a normal webcam in
Discord, Zoom, Google Meet, Teams, Chrome, etc.

Features:
- Real-time 30 FPS stream to 'OBS Virtual Camera'
- Live compact preview window showing what apps see
- Real-time mode switching transmitted directly to Discord/Zoom:
    [SPACE] or [M] : Enhanced Night Vision (B&W) <-> Thermal (Heatmap) <-> Raw IR
    [R]            : Re-ignite IR Flood Illuminator (resets hardware safety timeout)
    [H]            : Toggle HUD overlay
    [Q] or [ESC]   : Stop Virtual Camera bridge
"""

import asyncio
import sys
import time
import cv2
import numpy as np

import winsdk.windows.media.capture as wmc
import winsdk.windows.media.capture.frames as wmcf
import winsdk.windows.graphics.imaging as wgi
import winsdk.windows.storage.streams as streams

try:
    import pyvirtualcam
except ImportError:
    print("[-] Error: 'pyvirtualcam' package is missing.")
    print("[*] Run 'install.bat' or 'pip install -r requirements.txt' to install dependencies.")
    input("Press Enter to exit...")
    sys.exit(1)

MODES = ["Enhanced Night Vision (B&W)", "Thermal Heatmap (Color)", "Raw Infrared"]

async def init_ir_session():
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
        return None, None, 640, 360, 30

    settings = wmc.MediaCaptureInitializationSettings()
    settings.source_group = ir_group
    settings.streaming_capture_mode = wmc.StreamingCaptureMode.VIDEO
    settings.memory_preference = wmc.MediaCaptureMemoryPreference.CPU
    settings.sharing_mode = wmc.MediaCaptureSharingMode.SHARED_READ_ONLY

    media_capture = wmc.MediaCapture()
    try:
        await media_capture.initialize_async(settings)
    except Exception:
        settings.sharing_mode = wmc.MediaCaptureSharingMode.EXCLUSIVE_CONTROL
        await media_capture.initialize_async(settings)

    ir_source = None
    for _, src in media_capture.frame_sources.items():
        if src.info.source_kind == wmcf.MediaFrameSourceKind.INFRARED:
            ir_source = src
            break

    try:
        formats = list(ir_source.supported_formats)
        if formats:
            preferred = next((f for f in formats if f.frame_rate.numerator == 30), formats[0])
            await ir_source.set_format_async(preferred)
    except Exception:
        pass

    cf = ir_source.current_format
    w = cf.video_format.width if cf and cf.video_format else 640
    h = cf.video_format.height if cf and cf.video_format else 360
    fps_target = cf.frame_rate.numerator if cf and cf.frame_rate else 30

    reader = await media_capture.create_frame_reader_async(ir_source)
    status = await reader.start_async()
    if status != wmcf.MediaFrameReaderStartStatus.SUCCESS:
        return None, None, w, h, fps_target

    return media_capture, reader, w, h, fps_target

async def run_bridge():
    print("==========================================================")
    print("  Windows Hello IR Camera -> Virtual Webcam (Discord/Zoom)")
    print("==========================================================")
    print("[*] Connecting to Windows Hello IR sensor...")

    media_capture, reader, w, h, fps_target = await init_ir_session()
    if not reader:
        print("[-] Error: Windows Hello IR Camera not detected or could not connect.")
        input("Press Enter to exit...")
        return

    print(f"[+] Connected to IR sensor ({w}x{h} @ {fps_target} fps).")

    # Set up Virtual Camera
    try:
        vcam = pyvirtualcam.Camera(width=w, height=h, fps=fps_target, fmt=pyvirtualcam.PixelFormat.BGR)
        print(f"[+] Virtual camera device online: '{vcam.device}'")
        print("\n>>> IN DISCORD / ZOOM: Select 'OBS Virtual Camera' as your camera <<<")
        print("[*] Use preview window to toggle modes or re-ignite the IR LED.\n")
    except Exception as e:
        print(f"[-] Virtual camera error: {e}")
        if reader:
            await reader.stop_async()
        if media_capture:
            media_capture.close()
        input("Press Enter to exit...")
        return

    buf_len = w * h
    buf = streams.Buffer(buf_len)
    raw_bytes = bytearray(buf_len)
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))

    mode_idx = 0
    hud_visible = True
    notification_until = 0.0
    notification_msg = ""
    window_name = "IR Virtual Webcam Monitor (Broadcasting to Discord)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 640, 360)

    frame_count = 0
    start_time = time.time()

    try:
        with vcam:
            while True:
                frame = reader.try_acquire_latest_frame()
                if frame and frame.video_media_frame and frame.video_media_frame.software_bitmap:
                    sb = frame.video_media_frame.software_bitmap
                    converted = wgi.SoftwareBitmap.convert(sb, wgi.BitmapPixelFormat.GRAY8)
                    converted.copy_to_buffer(buf)

                    dr = streams.DataReader.from_buffer(buf)
                    dr.read_bytes(raw_bytes)
                    raw_img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w))

                    # Process frame
                    if mode_idx == 0:  # Enhanced Night Vision (B&W)
                        enhanced = clahe.apply(raw_img)
                        bgr_out = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
                    elif mode_idx == 1:  # Thermal Heatmap (Color)
                        enhanced = clahe.apply(raw_img)
                        bgr_out = cv2.applyColorMap(enhanced, cv2.COLORMAP_INFERNO)
                    else:  # Raw IR
                        bgr_out = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2BGR)

                    vcam.send(bgr_out)
                    vcam.sleep_until_next_frame()

                    # Render local preview monitor
                    preview = bgr_out.copy()
                    if hud_visible:
                        cv2.rectangle(preview, (0, 0), (w, 24), (25, 25, 25), -1)
                        status_str = f"Live on Discord: {MODES[mode_idx]}"
                        cv2.putText(preview, status_str, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 180), 1)

                        cv2.rectangle(preview, (0, h - 22), (w, h), (25, 25, 25), -1)
                        ctrl_str = "[SPACE/M] Mode  |  [R] Re-ignite LED  |  [Q] Exit"
                        cv2.putText(preview, ctrl_str, (8, h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1)

                        if time.time() < notification_until:
                            cv2.rectangle(preview, (140, 150), (500, 190), (0, 160, 0), -1)
                            cv2.putText(preview, notification_msg, (155, 176), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

                    cv2.imshow(window_name, preview)

                    frame_count += 1
                    if frame_count % 150 == 0:
                        elapsed = time.time() - start_time
                        fps = frame_count / elapsed
                        print(f"[*] Broadcasting: {frame_count} frames sent (~{fps:.1f} fps) - Mode: {MODES[mode_idx]}")

                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), 27):
                    break
                elif key in (ord('m'), ord('\t'), ord(' ')):
                    mode_idx = (mode_idx + 1) % len(MODES)
                    print(f"[+] Switched broadcast mode to: {MODES[mode_idx]}")
                elif key in (ord('r'), ord('R')):
                    print("[*] Re-igniting IR Illuminator...")
                    if reader:
                        try:
                            await reader.stop_async()
                        except Exception:
                            pass
                    if media_capture:
                        try:
                            media_capture.close()
                        except Exception:
                            pass
                    await asyncio.sleep(0.3)
                    media_capture, reader, w, h, fps_target = await init_ir_session()
                    notification_msg = "IR LED Re-ignited!"
                    notification_until = time.time() + 2.0
                    print("[+] Re-ignite complete.")
                elif key in (ord('h'), ord('H')):
                    hud_visible = not hud_visible

                await asyncio.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        if reader:
            await reader.stop_async()
        if media_capture:
            media_capture.close()
        cv2.destroyAllWindows()
        print("[+] IR Virtual Camera bridge stopped.")

def main():
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
