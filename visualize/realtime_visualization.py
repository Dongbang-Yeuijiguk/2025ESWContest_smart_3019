from __future__ import annotations

import argparse
import threading
import queue
import re
import ast
import sys
from collections import deque

import numpy as np
import serial
from serial.serialutil import SerialException
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

# -------------------- 사용자 정의 전처리 모듈 임포트 --------------------
# utils 폴더에 전처리 파일들이 있어야 합니다.
from utils.noise_filtering import dwt_denoise_matrix
from utils.pca import pca_52_subcarriers

# -------------------- CLI 인자 설정 --------------------
ap = argparse.ArgumentParser(description="Realtime ESP32 CSI Preprocessing and Visualization")
ap.add_argument("--port", default="/dev/ttyACM0", help="Serial port of the ESP32")
ap.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
ap.add_argument("--window-size", type=int, default=200, help="Number of CSI frames for the sliding window")
ap.add_argument("--n-components", type=int, default=1, help="Number of principal components to keep")
# y축 범위 고정 옵션 (미지정 시 첫 윈도우 기준으로 자동 고정)
ap.add_argument("--ymin", type=float, default=-80, help="Fixed y-axis minimum (processed signal plot)")
ap.add_argument("--ymax", type=float, default=80, help="Fixed y-axis maximum (processed signal plot)")
args = ap.parse_args()

# -------------------- 시리얼 포트 설정 --------------------
try:
    ser = serial.Serial(
        args.port, args.baud, timeout=0.2,
        bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE
    )
    ser.reset_input_buffer()
    print(f"[Serial] Opened {args.port} @ {args.baud}")
except SerialException as e:
    print(f"[Serial] Failed to open port: {e}", file=sys.stderr)
    sys.exit(1)

# -------------------- CSI 데이터 파서 --------------------
BRACKET_RE = re.compile(r'\[(.*?)\]')
# LLTF subcarriers (52 total), from esp32-csi-tool documentation
SUBCARRIER_IDXS = list(range(6, 32)) + list(range(33, 59))

def parse_csi_line(line: str) -> np.ndarray | None:
    """한 줄의 CSI 문자열을 파싱하여 52개 서브캐리어의 진폭 배열을 반환합니다."""
    if "CSI_DATA" not in line:
        return None

    match = BRACKET_RE.search(line)
    if not match:
        return None

    try:
        # 문자열을 정수 리스트로 변환
        values = ast.literal_eval("[" + match.group(1) + "]")
        if len(values) < 128:
            return None  # 데이터가 충분하지 않으면 무시

        # CSI는 I/Q 샘플이 번갈아 나옴 (imaginary, real, imaginary, real, ...)
        # esp32-csi-tool은 LLTF 필드의 64개 서브캐리어 값을 제공
        csi_raw = np.array(values, dtype=np.int8)

        # 복소수 형태로 변환: c = Q + i*I
        csi_cmplx = csi_raw[1:129:2] + 1j * csi_raw[0:128:2]

        # 진폭 계산
        csi_amp = np.abs(csi_cmplx)

        # 논문/연구에서 주로 사용하는 52개 서브캐리어만 선택
        return csi_amp[SUBCARRIER_IDXS]

    except (ValueError, SyntaxError):
        return None

# -------------------- 시리얼 리더 스레드 --------------------
# UI 멈춤을 방지하기 위해 별도 스레드에서 시리얼 데이터를 읽음
q = queue.Queue(maxsize=5000)
stop_flag = False

def reader_thread():
    while not stop_flag:
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore").strip()
            if line:
                q.put_nowait(line)
        except queue.Full:
            # 큐가 가득 차면 오래된 데이터를 버림
            pass
        except Exception:
            break  # 스레드 종료
    print("[Serial] Reader thread stopped.")

threading.Thread(target=reader_thread, daemon=True).start()

# -------------------- PyQtGraph UI 설정 --------------------
pg.setConfigOptions(antialias=True)
app = pg.mkQApp("CSI Realtime Pipeline")
win = pg.GraphicsLayoutWidget(show=True, title="CSI Realtime Preprocessing Pipeline")
win.resize(1200, 800)

# 1. 원본 CSI 진폭 히트맵
p1 = win.addPlot(row=0, col=0, title="Raw CSI Amplitude (Sliding Window)")
p1.setLabel("left", "Subcarrier Index")
p1.setLabel("bottom", "Time (frames)")
img = pg.ImageItem(border='w')
p1.addItem(img)
# 색상 맵/컬러바 설정 (필요 시 setLevels로 고정 가능)
cmap = pg.colormap.get("viridis")
bar = pg.ColorBarItem(values=(0, 30), colorMap=cmap)
bar.setImageItem(img)

# 2. 최종 전처리된 신호
p2 = win.addPlot(row=1, col=0, title="Processed Signal (DWT -> PCA)")
p2.setLabel("left", "Principal Component Amplitude")
p2.setLabel("bottom", "Time (frames)")
p2.showGrid(x=True, y=True, alpha=0.3)
curve = p2.plot(pen=pg.mkPen('y', width=2))

# y축을 한 번만 고정하기 위한 플래그/범위
_y_axis_locked = False
_ymin_fixed = None
_ymax_fixed = None

# -------------------- 데이터 버퍼 및 업데이트 함수 --------------------
csi_amplitude_buffer = deque(maxlen=args.window_size)

def _lock_y_axis_once(ydata: np.ndarray):
    """처음 한 번만 y축 범위를 고정한다."""
    global _y_axis_locked, _ymin_fixed, _ymax_fixed

    if _y_axis_locked:
        return

    if args.ymin is not None and args.ymax is not None:
        ymin, ymax = float(args.ymin), float(args.ymax)
    else:
        # 데이터 기반 합리적 초기 범위(1~99 퍼센타일) + 5% 패딩
        lo, hi = np.percentile(ydata, [1, 99])
        pad = 0.05 * max(1e-9, (hi - lo))
        ymin, ymax = lo - pad, hi + pad
        if ymin == ymax:  # 상수 신호 방지
            ymin, ymax = ymin - 1.0, ymax + 1.0

    _ymin_fixed, _ymax_fixed = ymin, ymax
    p2.setYRange(_ymin_fixed, _ymax_fixed)
    p2.enableAutoRange('y', False)  # y축 고정
    _y_axis_locked = True

def update():
    """타이머에 의해 주기적으로 호출되어 데이터 처리 및 시각화를 수행합니다."""
    processed_count = 0
    while not q.empty() and processed_count < 100:  # 한 번에 너무 많은 프레임 처리 방지
        line = q.get_nowait()
        amps = parse_csi_line(line)
        if amps is not None and amps.shape == (52,):
            csi_amplitude_buffer.append(amps)
            processed_count += 1

    # 버퍼에 충분한 데이터가 쌓였는지 확인
    if len(csi_amplitude_buffer) < args.window_size:
        return

    # --- 데이터 전처리 파이프라인 ---
    # 1) 버퍼 데이터를 (window_size, 52) 형태의 numpy 배열로 변환
    amp_matrix = np.array(csi_amplitude_buffer)

    # 2) DWT 잡음 제거
    denoised_amp = dwt_denoise_matrix(amp_matrix)

    # 3) PCA 차원 축소
    pca_amp = pca_52_subcarriers(denoised_amp, n_components=args.n_components)

    # --- 시각화 업데이트 ---
    # 히트맵 업데이트 (pyqtgraph는 (x, y) 순서이므로 전치 필요)
    img.setImage(amp_matrix.T)

    # 라인 플롯 업데이트
    ydata = pca_amp.flatten()
    curve.setData(ydata)

    # y축을 처음 한 번만 고정
    _lock_y_axis_once(ydata)

# -------------------- 메인 실행 로직 --------------------
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)  # 50ms 마다 update 함수 호출 (20 FPS)

if __name__ == "__main__":
    print("[+] Starting real-time visualization. Close the window to exit.")
    try:
        pg.exec()
    finally:
        stop_flag = True
        try:
            ser.close()
            print("[Serial] Port closed.")
        except Exception as e:
            print(f"[Serial] Error closing port: {e}")