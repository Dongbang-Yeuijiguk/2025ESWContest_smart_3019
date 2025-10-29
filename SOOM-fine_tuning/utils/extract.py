# utils/extract.py
# CSI 데이터에서 진폭과 위상을 추출하는 함수

import numpy as np
import pandas as pd
import ast

def amp_phase_from_csi(data, column='data'):
    """
    data  : pd.DataFrame 또는 pd.Series
    column: DataFrame일 때 CSI 문자열이 있는 컬럼명 (기본: 'data')
    return: Amp (N,52), Pha (N,52)
    """
    # --- Series 확보 ---
    if isinstance(data, pd.DataFrame):
        s = data[column]
    else:
        s = data  # 이미 Series인 경우

    N = len(s)
    AmpCSI   = np.zeros((N, 64), dtype=np.float64)
    PhaseCSI = np.zeros((N, 64), dtype=np.float64)

    for i in range(N):
        item = s.iat[i]  # 정수 위치 인덱싱 (KeyError 방지)
        if pd.isna(item):
            # 결측이면 0 그대로 두고 진행
            continue

        # 문자열 -> 리스트 안전 파싱
        if isinstance(item, str):
            values = ast.literal_eval(item.strip())
        else:
            # 이미 리스트/배열 형태라면 리스트로 변환
            values = list(item)

        # 실/허 교차 시퀀스 길이 보정 (앞 64쌍 = 128개만 사용)
        if len(values) < 2*64:
            # 필요하면 패딩 정책으로 바꿔도 됨 (여기선 스킵)
            # 예: values = (values + [0]*(2*64 - len(values)))[:2*64]
            raise ValueError(f"[row {i}] 값이 128개 미만: len={len(values)}")
        values = values[:2*64]

        # 짝수=Im, 홀수=Re (질문에서의 가정 유지)
        ImCSI = np.asarray(values[::2], dtype=np.int64)   # (64,)
        ReCSI = np.asarray(values[1::2], dtype=np.int64)  # (64,)

        # 진폭/위상
        AmpCSI[i, :]   = np.hypot(ImCSI, ReCSI)          # = sqrt(Im^2 + Re^2)
        PhaseCSI[i, :] = np.arctan2(ImCSI, ReCSI)        # arctan2(y=Im, x=Re)

    # 서브캐리어 선택: 0-based로 6..31, 33..58 -> 슬라이스 6:32, 33:59
    Amp = np.concatenate([AmpCSI[:, 6:32],   AmpCSI[:, 33:59]], axis=1)  # (N,52)
    Pha = np.concatenate([PhaseCSI[:, 6:32], PhaseCSI[:, 33:59]], axis=1)  # (N,52)
    return Amp, Pha

