"""Screen / window capture engine.

Captures a monitor or individual window at up to 60 fps using
Windows Graphics Capture (hardware-accelerated) with a GDI/mss
fallback.  During recording, raw BGRA frames are piped to ffmpeg
for lossless AVI encoding.  Non-recording mode emits QImage preview
frames via the ``frame_ready`` signal.
"""

import logging
import time
import threading
import tempfile
import os
import subprocess

logger = logging.getLogger(__name__)
import ctypes
from typing import Optional, List

import numpy as np
import cv2
import mss

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

# Windows Graphics Capture API (hardware-accelerated capture)
try:
    from windows_capture import WindowsCapture, Frame, InternalCaptureControl
    _HAS_WGC = True
except ImportError:
    _HAS_WGC = False

# Windows high-resolution timer
try:
    _winmm = ctypes.windll.winmm
except AttributeError:
    _winmm = None


from .utils import ffmpeg_exe as _ffmpeg_exe, subprocess_kwargs as _subprocess_kwargs


def _precise_sleep(seconds: float) -> None:
    """Hybrid sleep: coarse sleep then spin-wait for sub-ms accuracy."""
    if seconds <= 0:
        return
    # Sleep most of the time (leave 2ms for spin-wait)
    coarse = seconds - 0.002
    if coarse > 0:
        time.sleep(coarse)
    # Spin-wait the remaining time for precision
    target = time.perf_counter() + (seconds - max(coarse, 0))
    while time.perf_counter() < target:
        pass


def _start_ffmpeg_writer(
    out_path: str, w: int, h: int, fps: int,
) -> Optional[subprocess.Popen]:
    """Launch an ffmpeg subprocess that accepts raw BGRA on stdin → lossless AVI.

    Returns the Popen object, or None if ffmpeg couldn't start.
    """
    try:
        ffmpeg = _ffmpeg_exe()
        cmd = [
            ffmpeg,
            "-y",                        # overwrite
            "-f", "rawvideo",
            "-pix_fmt", "bgra",
            "-s", f"{w}x{h}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "huffyuv",           # very fast lossless, ~2:1 compression
            out_path,
        ]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,      # capture errors for diagnostics
            **_subprocess_kwargs(),
        )
        # Give ffmpeg a moment to fail on bad args
        import time as _t
        _t.sleep(0.05)
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            logger.error("ffmpeg exited immediately: %s", stderr[:300])
            return None
        return proc
    except Exception as exc:
        logger.error("ffmpeg pipe launch failed: %s", exc)
        return None


def _stop_ffmpeg_writer(proc: Optional[subprocess.Popen]) -> None:
    """Cleanly close an ffmpeg writer subprocess."""
    if proc is None:
        return
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    # Log any errors
    if proc.stderr:
        try:
            tail = proc.stderr.read().decode(errors="replace").strip()
            if tail and proc.returncode != 0:
                logger.warning("ffmpeg stderr: %s", tail[-300:])
        except Exception:
            pass


class ScreenRecorder(QObject):
    """Captures a monitor, emits preview frames, and optionally records to file."""

    frame_ready = Signal(QImage)
    recording_finished = Signal(str)  # output path
    capture_backend_changed = Signal(str)  # "DXGI" or "GDI"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor_index: int = 1
        self._capturing: bool = False
        self._recording: bool = False
        self._output_path: str = ""
        self._thread: Optional[threading.Thread] = None
        self._fps: int = 30
        self._start_time: float = 0.0
        self._actual_fps: float = 30.0
        self._frame_count: int = 0
        self._frame_timestamps: List[float] = []  # ms offset per frame
        self._lock = threading.Lock()
        # window capture mode
        self._capture_mode: str = "monitor"  # "monitor" | "window"
        self._window_hwnd: int = 0
        self._initial_size: tuple = (0, 0)
        self._backend: str = ""  # set once capture starts
        # WGC shared frame buffer (written by callback, read by loop)
        self._wgc_frame: Optional[np.ndarray] = None
        self._wgc_frame_lock = threading.Lock()
        self._wgc_control = None

    # ── static helpers ──────────────────────────────────────────────

    @staticmethod
    def get_monitors() -> List[dict]:
        """Return a list of available monitors with dimensions and positions."""
        with mss.mss() as sct:
            monitors: List[dict] = []
            for i, m in enumerate(sct.monitors):
                if i == 0:  # "all monitors" virtual screen
                    continue
                monitors.append(
                    {
                        "index": i,
                        "name": f"Display {i}  ({m['width']}×{m['height']})",
                        "width": m["width"],
                        "height": m["height"],
                        "left": m["left"],
                        "top": m["top"],
                    }
                )
            return monitors

    @staticmethod
    def capture_thumbnail(monitor_index: int) -> Optional[QImage]:
        """Grab a single frame from a monitor and return a scaled thumbnail."""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[monitor_index]
                img = sct.grab(monitor)
                frame = np.asarray(img)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                h, w = frame_rgb.shape[:2]
                scale = min(280 / w, 160 / h)
                thumb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
                qimg = QImage(
                    thumb.data,
                    thumb.shape[1],
                    thumb.shape[0],
                    thumb.strides[0],
                    QImage.Format.Format_RGB888,
                )
                return qimg.copy()
        except Exception:
            return None

    # ── properties ──────────────────────────────────────────────────

    @property
    def is_capturing(self) -> bool:
        return self._capturing

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def recording_duration_ms(self) -> float:
        if not self._recording or self._start_time == 0:
            return 0
        return (time.time() - self._start_time) * 1000

    @property
    def actual_fps(self) -> float:
        """The real measured FPS of the last recording."""
        return self._actual_fps

    @property
    def frame_count(self) -> int:
        """Number of frames written to the pipe during the last recording."""
        return self._frame_count

    @property
    def frame_timestamps(self) -> List[float]:
        """Per-frame timestamps (ms from recording start) for each written frame."""
        return list(self._frame_timestamps)

    @property
    def backend(self) -> str:
        """Current capture backend: 'DXGI' or 'GDI' (mss)."""
        return self._backend

    # ── public API ──────────────────────────────────────────────────

    def start_capture(self, monitor_index: int, fps: int = 60) -> None:
        """Begin capturing a monitor for live preview (no recording yet)."""
        self.stop_capture()
        self._capture_mode = "monitor"
        self._monitor_index = monitor_index
        self._fps = fps
        self._capturing = True
        self._recording = False
        self._thread = threading.Thread(target=self._capture_loop, daemon=False)
        self._thread.start()

    def start_capture_window(self, hwnd: int, fps: int = 60) -> None:
        """Start capturing a specific window by its handle."""
        self.stop_capture()
        self._capture_mode = "window"
        self._window_hwnd = hwnd
        self._fps = fps
        self._capturing = True
        self._recording = False
        from .window_utils import get_window_rect
        rect = get_window_rect(hwnd)
        if rect:
            self._initial_size = (rect["width"], rect["height"])
        else:
            self._initial_size = (0, 0)
        self._thread = threading.Thread(target=self._capture_loop_window, daemon=False)
        self._thread.start()

    def start_recording(self, start_time: float = 0.0) -> str:
        """Begin writing captured frames to a temp video file. Returns path.

        *start_time* — ``time.time()`` epoch shared with activity trackers
        so all timestamps are relative to the same origin.  If 0 the current
        wall-clock is used.
        """
        temp_path = os.path.join(
            tempfile.gettempdir(), f"followcursor_{int(time.time())}.avi"
        )
        with self._lock:
            self._output_path = temp_path
            self._start_time = start_time if start_time > 0 else time.time()
            self._frame_count = 0
            self._frame_timestamps = []
            self._recording = True
        return temp_path

    def stop_recording(self) -> str:
        """Stop recording and return the path to the raw AVI file."""
        with self._lock:
            self._recording = False
            elapsed = time.time() - self._start_time
            if elapsed > 0 and self._frame_count > 0:
                self._actual_fps = self._frame_count / elapsed
            else:
                self._actual_fps = float(self._fps)
            return self._output_path

    def stop_capture(self) -> None:
        """Stop the capture thread and release all resources."""
        self._capturing = False
        self._recording = False
        if self._thread:
            self._thread.join()
            self._thread = None

    # ── internal ────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Monitor capture — prefers WGC hardware capture, falls back to mss."""
        if _winmm:
            _winmm.timeBeginPeriod(1)
        try:
            if _HAS_WGC:
                try:
                    self._capture_loop_wgc(monitor_index=self._monitor_index)
                    return
                except Exception as exc:
                    logger.warning("WGC capture failed: %r", exc)
                    logger.info("Falling back to GDI (mss)")
            self._backend = "GDI"
            self.capture_backend_changed.emit("GDI")
            self._capture_loop_mss()
        finally:
            if _winmm:
                _winmm.timeEndPeriod(1)

    def _capture_loop_wgc(
        self,
        monitor_index: Optional[int] = None,
        window_hwnd: Optional[int] = None,
    ) -> None:
        """Hardware-accelerated capture via Windows Graphics Capture API.

        Works for both monitor capture (pass monitor_index) and window
        capture (pass window_hwnd).  The WGC callback writes BGRA frames
        into a shared buffer; this loop polls it at the target FPS.
        """
        self._backend = "WGC"
        self.capture_backend_changed.emit("WGC")

        # Resolve window_hwnd → window_name (WGC v1.5 uses title string)
        window_name: Optional[str] = None
        if window_hwnd is not None:
            _user32 = ctypes.windll.user32
            length = _user32.GetWindowTextLengthW(window_hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(window_hwnd, buf, length + 1)
                window_name = buf.value
            if not window_name:
                raise RuntimeError("WGC: cannot get window title from HWND")

        # Get expected dimensions from mss (used for VideoWriter init)
        if monitor_index is not None:
            with mss.mss() as sct:
                mon_info = sct.monitors[monitor_index]
                w, h = mon_info["width"], mon_info["height"]
        elif window_hwnd is not None:
            from .window_utils import get_window_rect
            rect = get_window_rect(window_hwnd)
            if not rect:
                raise RuntimeError("WGC: target window not found")
            w, h = rect["width"], rect["height"]
        else:
            raise ValueError("monitor_index or window_hwnd required")

        # ── shared state written by the WGC callback ──────────────
        self._wgc_frame = None
        self._wgc_frame_new = False  # flag: callback delivered a fresh frame
        frame_dims = [w, h]  # updated by callback if source resizes

        def _on_frame(frame: Frame, ctl: InternalCaptureControl) -> None:
            """Stash the latest BGRA numpy array (zero‑copy view → copy)."""
            buf = frame.frame_buffer
            if buf is None:
                return
            with self._wgc_frame_lock:
                self._wgc_frame = buf.copy()  # BGRA uint8, (H, W, 4)
                self._wgc_frame_new = True
                frame_dims[0] = frame.width
                frame_dims[1] = frame.height
            if not self._capturing:
                ctl.stop()

        def _on_closed() -> None:
            pass

        # ── build and start the WGC session ───────────────────────
        capture = WindowsCapture(
            cursor_capture=False,   # we render our own cursor in export
            draw_border=False,
            monitor_index=monitor_index,
            window_name=window_name,
        )
        capture.frame_handler = _on_frame
        capture.closed_handler = _on_closed
        capture_control = capture.start_free_threaded()
        self._wgc_control = capture_control

        try:
            # Wait for the first non‑None frame (up to 3 s)
            deadline = time.monotonic() + 3.0
            while self._capturing and time.monotonic() < deadline:
                with self._wgc_frame_lock:
                    if self._wgc_frame is not None:
                        break
                time.sleep(0.01)
            with self._wgc_frame_lock:
                if self._wgc_frame is None:
                    raise RuntimeError("WGC: no frames received within 3 seconds")

            writer_proc: Optional[subprocess.Popen] = None
            writer_cv: Optional[cv2.VideoWriter] = None
            was_recording = False

            while self._capturing:
                t0 = time.perf_counter()

                with self._lock:
                    is_recording = self._recording
                    output_path = self._output_path

                # ── state transitions (start / stop recording) ────
                cur_w, cur_h = frame_dims
                if is_recording and not was_recording:
                    out_path = output_path
                    if not out_path.lower().endswith(".avi"):
                        out_path = output_path.rsplit(".", 1)[0] + ".avi"
                        with self._lock:
                            self._output_path = out_path
                    # Try ffmpeg pipe (fast, out-of-process encoding)
                    writer_proc = _start_ffmpeg_writer(out_path, w, h, self._fps)
                    if writer_proc is None:
                        # Fallback: cv2 with MJPG
                        logger.warning("Falling back to cv2.VideoWriter MJPG")
                        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                        writer_cv = cv2.VideoWriter(out_path, fourcc, self._fps, (w, h))
                    was_recording = True
                elif not is_recording and was_recording:
                    _stop_ffmpeg_writer(writer_proc)
                    writer_proc = None
                    if writer_cv:
                        writer_cv.release()
                        writer_cv = None
                    self.recording_finished.emit(output_path)
                    was_recording = False

                # ── grab latest frame from WGC callback buffer ────
                with self._wgc_frame_lock:
                    frame_bgra = self._wgc_frame
                    is_new = self._wgc_frame_new
                    self._wgc_frame_new = False

                if frame_bgra is None:
                    time.sleep(0.001)
                    continue

                # Skip processing if no new frame (duplicate)
                if not is_new:
                    elapsed = time.perf_counter() - t0
                    sleep_time = max(0, (1.0 / self._fps) - elapsed)
                    if sleep_time > 0:
                        _precise_sleep(sleep_time)
                    continue

                fh, fw = frame_bgra.shape[:2]

                if was_recording:
                    if fw != w or fh != h:
                        frame_bgra = cv2.resize(frame_bgra, (w, h))

                    if writer_proc and writer_proc.stdin and not writer_proc.stdin.closed:
                        try:
                            writer_proc.stdin.write(
                                frame_bgra.tobytes()
                                if frame_bgra.flags["C_CONTIGUOUS"]
                                else np.ascontiguousarray(frame_bgra).tobytes()
                            )
                            with self._lock:
                                ts = (time.time() - self._start_time) * 1000.0
                                self._frame_timestamps.append(ts)
                                self._frame_count += 1
                        except (BrokenPipeError, OSError) as exc:
                            logger.error("ffmpeg pipe write error: %s", exc)
                            _stop_ffmpeg_writer(writer_proc)
                            writer_proc = None
                    elif writer_cv:
                        frame_bgr = frame_bgra[:, :, :3]
                        writer_cv.write(np.ascontiguousarray(frame_bgr))
                        with self._lock:
                            ts = (time.time() - self._start_time) * 1000.0
                            self._frame_timestamps.append(ts)
                            self._frame_count += 1
                else:
                    # Preview: BGRA → RGBA (just swap R/B, keep alpha)
                    # QImage Format_RGBA8888 avoids a separate RGB copy
                    if fw != w or fh != h:
                        frame_bgra = cv2.resize(frame_bgra, (w, h))
                    frame_rgba = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2RGBA)
                    qimg = QImage(
                        frame_rgba.data,
                        w,
                        h,
                        frame_rgba.strides[0],
                        QImage.Format.Format_RGBA8888,
                    ).copy()
                    self.frame_ready.emit(qimg)

                # ── frame‑rate cap ────────────────────────────────
                elapsed = time.perf_counter() - t0
                sleep_time = max(0, (1.0 / self._fps) - elapsed)
                if sleep_time > 0:
                    _precise_sleep(sleep_time)

            # cleanup
            _stop_ffmpeg_writer(writer_proc)
            if writer_cv:
                writer_cv.release()
            if was_recording:
                self.recording_finished.emit(output_path)
        finally:
            try:
                capture_control.stop()
            except Exception:
                pass
            self._wgc_control = None
            self._wgc_frame = None

    def _capture_loop_mss(self) -> None:
        """GDI-based monitor capture via mss (fallback)."""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[self._monitor_index]
                w, h = monitor["width"], monitor["height"]
                writer_proc: Optional[subprocess.Popen] = None
                writer_cv: Optional[cv2.VideoWriter] = None
                was_recording = False
                record_fps = min(self._fps, 30)

                while self._capturing:
                    t0 = time.perf_counter()

                    with self._lock:
                        is_recording = self._recording
                        output_path = self._output_path

                    # state transitions
                    if is_recording and not was_recording:
                        out_path = output_path
                        if not out_path.lower().endswith(".avi"):
                            out_path = output_path.rsplit(".", 1)[0] + ".avi"
                            with self._lock:
                                self._output_path = out_path
                        writer_proc = _start_ffmpeg_writer(out_path, w, h, record_fps)
                        if writer_proc is None:
                            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                            writer_cv = cv2.VideoWriter(out_path, fourcc, record_fps, (w, h))
                        if record_fps != self._fps:
                            logger.info("GDI recording capped at %d fps for stability", record_fps)
                        was_recording = True
                    elif not is_recording and was_recording:
                        _stop_ffmpeg_writer(writer_proc)
                        writer_proc = None
                        if writer_cv:
                            writer_cv.release()
                            writer_cv = None
                        self.recording_finished.emit(output_path)
                        was_recording = False

                    # grab frame (BGRA from mss)
                    img = sct.grab(monitor)
                    frame = np.asarray(img)

                    if was_recording:
                        if writer_proc and writer_proc.stdin and not writer_proc.stdin.closed:
                            try:
                                writer_proc.stdin.write(frame.tobytes())
                                with self._lock:
                                    ts = (time.time() - self._start_time) * 1000.0
                                    self._frame_timestamps.append(ts)
                                    self._frame_count += 1
                            except (BrokenPipeError, OSError):
                                _stop_ffmpeg_writer(writer_proc)
                                writer_proc = None
                        elif writer_cv:
                            frame_bgr = np.ascontiguousarray(frame[:, :, :3])
                            writer_cv.write(frame_bgr)
                            with self._lock:
                                ts = (time.time() - self._start_time) * 1000.0
                                self._frame_timestamps.append(ts)
                                self._frame_count += 1
                    else:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                        qimg = QImage(
                            frame_rgb.data,
                            w,
                            h,
                            frame_rgb.strides[0],
                            QImage.Format.Format_RGB888,
                        ).copy()
                        self.frame_ready.emit(qimg)

                    # frame-rate cap (precise timing)
                    elapsed = time.perf_counter() - t0
                    sleep_time = max(0, (1.0 / self._fps) - elapsed)
                    if sleep_time > 0:
                        _precise_sleep(sleep_time)

                # cleanup
                _stop_ffmpeg_writer(writer_proc)
                if writer_cv:
                    writer_cv.release()
                if was_recording:
                    self.recording_finished.emit(output_path)
        except Exception as exc:
            logger.error("mss capture error: %s", exc)

    def _capture_loop_window(self) -> None:
        """Capture loop for a specific window — prefers WGC, falls back to mss."""
        if _winmm:
            _winmm.timeBeginPeriod(1)
        try:
            if _HAS_WGC:
                try:
                    self._capture_loop_wgc(window_hwnd=self._window_hwnd)
                    return
                except Exception as exc:
                    logger.warning("WGC window capture failed: %r", exc)
                    logger.info("Falling back to GDI (mss) for window")

            # ── GDI fallback for window capture ───────────────────
            from .window_utils import get_window_rect

            self._backend = "GDI"
            self.capture_backend_changed.emit("GDI")

            with mss.mss() as sct:
                rect = get_window_rect(self._window_hwnd)
                if not rect:
                    return
                w, h = self._initial_size
                if w == 0 or h == 0:
                    w, h = rect["width"], rect["height"]
                    self._initial_size = (w, h)

                writer_proc: Optional[subprocess.Popen] = None
                writer_cv: Optional[cv2.VideoWriter] = None
                was_recording = False

                while self._capturing:
                    t0 = time.perf_counter()

                    with self._lock:
                        is_recording = self._recording
                        output_path = self._output_path

                    rect = get_window_rect(self._window_hwnd)
                    if not rect:
                        _stop_ffmpeg_writer(writer_proc)
                        if writer_cv:
                            writer_cv.release()
                        if was_recording:
                            self.recording_finished.emit(output_path)
                        self._capturing = False
                        break

                    if is_recording and not was_recording:
                        out_path = output_path
                        if not out_path.lower().endswith(".avi"):
                            out_path = output_path.rsplit(".", 1)[0] + ".avi"
                            with self._lock:
                                self._output_path = out_path
                        record_fps = min(self._fps, 30)
                        writer_proc = _start_ffmpeg_writer(out_path, w, h, record_fps)
                        if writer_proc is None:
                            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                            writer_cv = cv2.VideoWriter(out_path, fourcc, record_fps, (w, h))
                        if record_fps != self._fps:
                            logger.info("GDI window recording capped at %d fps for stability", record_fps)
                        was_recording = True
                    elif not is_recording and was_recording:
                        _stop_ffmpeg_writer(writer_proc)
                        writer_proc = None
                        if writer_cv:
                            writer_cv.release()
                            writer_cv = None
                        self.recording_finished.emit(output_path)
                        was_recording = False

                    monitor = {
                        "left": rect["left"],
                        "top": rect["top"],
                        "width": rect["width"],
                        "height": rect["height"],
                    }
                    img = sct.grab(monitor)
                    frame = np.asarray(img)
                    cw, ch = rect["width"], rect["height"]

                    if was_recording:
                        if cw != w or ch != h:
                            frame = cv2.resize(frame, (w, h))
                        if writer_proc and writer_proc.stdin and not writer_proc.stdin.closed:
                            try:
                                writer_proc.stdin.write(frame.tobytes())
                                with self._lock:
                                    ts = (time.time() - self._start_time) * 1000.0
                                    self._frame_timestamps.append(ts)
                                    self._frame_count += 1
                            except (BrokenPipeError, OSError):
                                _stop_ffmpeg_writer(writer_proc)
                                writer_proc = None
                        elif writer_cv:
                            frame_bgr = np.ascontiguousarray(frame[:, :, :3])
                            writer_cv.write(frame_bgr)
                            with self._lock:
                                ts = (time.time() - self._start_time) * 1000.0
                                self._frame_timestamps.append(ts)
                                self._frame_count += 1
                    else:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                        if cw != w or ch != h:
                            frame_rgb = cv2.resize(frame_rgb, (w, h))
                        qimg = QImage(
                            frame_rgb.data, w, h,
                            frame_rgb.strides[0],
                            QImage.Format.Format_RGB888,
                        ).copy()
                        self.frame_ready.emit(qimg)

                    elapsed = time.perf_counter() - t0
                    sleep_time = max(0, (1.0 / self._fps) - elapsed)
                    if sleep_time > 0:
                        _precise_sleep(sleep_time)

                _stop_ffmpeg_writer(writer_proc)
                if writer_cv:
                    writer_cv.release()
                if was_recording:
                    self.recording_finished.emit(output_path)
        except Exception as exc:
            logger.error("window capture error: %s", exc)
        finally:
            if _winmm:
                _winmm.timeEndPeriod(1)
