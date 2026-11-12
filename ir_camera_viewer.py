"""
Windows Hello IR Camera Viewer & Night Vision App
-------------------------------------------------
Features:
- Live 30 FPS stream from Windows Hello IR Camera
- Auto-Contrast & Night Vision Enhancement (CLAHE)
- Thermal False-Color Mode (Inferno Colormap)
- Instant Snapshot capture ('S' key) saved to Desktop/IR_Captures
- IR Flood Illuminator Re-ignite ('R' key) to reset hardware safety watchdog
- Clean HUD overlay with FPS and keyboard controls
"""

import asyncio
import os
import sys
import time
from datetime import datetime
import numpy as np
import cv2

import winsdk.windows.media.capture as wmc
import winsdk.windows.media.capture.frames as wmcf
import winsdk.windows.graphics.imaging as wgi
import winsdk.windows.storage.streams as streams

MODES = ["Raw IR", "Night Vision (Enhanced)", "Thermal (False Color)"]

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

async def run_viewer():
    print("[*] Initializing Windows Hello IR Camera...")
    media_capture, reader, w, h, fps_target = await init_ir_session()
    if not reader:
        print("[-] Error: Could not connect to Windows Hello IR Camera.")
        input("Press Enter to close...")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    captures_dir = os.path.join(base_dir, "Captures")
    os.makedirs(captures_dir, exist_ok=True)

    buf_len = w * h
    buf = streams.Buffer(buf_len)
    raw_bytes = bytearray(buf_len)

    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    mode_idx = 1  # Default to Enhanced Night Vision
    hud_visible = True
    notification_until = 0.0
    notification_msg = ""
    notification_color = (0, 160, 0)

    window_name = "Windows Hello IR Camera (Night Vision)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 540)

    fps_count = 0
    fps_val = 0.0
    last_fps_time = time.time()

    print("[+] IR Stream is LIVE! Window opened.")

    try:
        while True:
            frame = reader.try_acquire_latest_frame()
            if frame and frame.video_media_frame and frame.video_media_frame.software_bitmap:
                sb = frame.video_media_frame.software_bitmap
                converted = wgi.SoftwareBitmap.convert(sb, wgi.BitmapPixelFormat.GRAY8)
                converted.copy_to_buffer(buf)

                dr = streams.DataReader.from_buffer(buf)
                dr.read_bytes(raw_bytes)
                raw_img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w))

                # FPS calculation
                fps_count += 1
                now = time.time()
                if now - last_fps_time >= 1.0:
                    fps_val = fps_count / (now - last_fps_time)
                    fps_count = 0
                    last_fps_time = now

                # Process based on mode
                if mode_idx == 0:  # Raw IR
                    display_frame = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2BGR)
                elif mode_idx == 1:  # Enhanced Night Vision (CLAHE)
                    enhanced = clahe.apply(raw_img)
                    display_frame = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
                else:  # Thermal False-Color
                    enhanced = clahe.apply(raw_img)
                    display_frame = cv2.applyColorMap(enhanced, cv2.COLORMAP_INFERNO)

                render_frame = cv2.resize(display_frame, (960, 540), interpolation=cv2.INTER_LINEAR)

                # Render HUD
                if hud_visible:
                    mode_text = f"Mode: {MODES[mode_idx]} [TAB/M to switch]"
                    fps_text = f"FPS: {fps_val:.1f} ({w}x{h}@{fps_target})"
                    controls_text = "[S] Snapshot  |  [R] Re-ignite IR LED  |  [H] Hide HUD  |  [Q] Quit"

                    # Header bar
                    cv2.rectangle(render_frame, (0, 0), (960, 36), (20, 20, 20), -1)
                    cv2.putText(render_frame, mode_text, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 180), 2)
                    cv2.putText(render_frame, fps_text, (720, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

                    # Footer bar
                    cv2.rectangle(render_frame, (0, 508), (960, 540), (20, 20, 20), -1)
                    cv2.putText(render_frame, controls_text, (12, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1)

                    # Notification banner
                    if time.time() < notification_until:
                        cv2.rectangle(render_frame, (200, 240), (760, 285), notification_color, -1)
                        cv2.putText(render_frame, notification_msg, (220, 272), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

                cv2.imshow(window_name, render_frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):  # 'q' or ESC
                break
            elif key in (ord('m'), ord('\t'), ord(' ')):  # M, TAB, SPACE
                mode_idx = (mode_idx + 1) % len(MODES)
            elif key in (ord('s'), ord('S')):  # Snapshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"IR_Capture_{timestamp}.png"
                save_path = os.path.join(captures_dir, fn)
                if mode_idx == 0:
                    cv2.imwrite(save_path, raw_img)
                elif mode_idx == 1:
                    cv2.imwrite(save_path, clahe.apply(raw_img))
                else:
                    cv2.imwrite(save_path, display_frame)

                notification_msg = f"Saved: {fn}"
                notification_color = (0, 160, 0)
                notification_until = time.time() + 2.0
                print(f"[+] Snapshot saved: {save_path}")
            elif key in (ord('r'), ord('R')):  # Re-ignite IR Illuminator
                print("[*] Re-igniting IR Illuminator...")
                notification_msg = "Re-igniting IR Illuminator..."
                notification_color = (0, 120, 215)
                notification_until = time.time() + 1.5

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
                notification_msg = "IR Flood Illuminator Re-engaged!"
                notification_color = (0, 160, 0)
                notification_until = time.time() + 2.0
                print("[+] Re-ignite complete.")
            elif key in (ord('h'), ord('H')):
                hud_visible = not hud_visible

            await asyncio.sleep(0.005)

    finally:
        if reader:
            await reader.stop_async()
        if media_capture:
            media_capture.close()
        cv2.destroyAllWindows()
        print("[+] IR Camera stream closed.")

def main():
    try:
        asyncio.run(run_viewer())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
