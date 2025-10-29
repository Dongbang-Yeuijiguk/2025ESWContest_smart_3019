import numpy as np

def kalman_denoise_1d(
    z: np.ndarray,
    q: float | None = None,
    r: float | None = None,
    q_factor: float = 0.01,
    init_x: float | None = None,
    init_P: float | None = None,
) -> np.ndarray:
    """
    1D 칼만 필터 (random walk 모델)로 신호 z를 평활화.
    x_t = x_{t-1} + w_t,   z_t = x_t + v_t
    w ~ N(0, q), v ~ N(0, r)

    Args:
        z: (T,) 관측 시계열
        q: 프로세스 잡음 분산 (없으면 r 기반으로 q_factor*r 사용)
        r: 측정 잡음 분산 (없으면 diff 분산으로 추정: var(diff(z))/2)
        q_factor: q가 None일 때 q = q_factor * r
        init_x: 초기 상태 (없으면 z[0])
        init_P: 초기 공분산 (없으면 r 또는 1.0)

    Returns:
        x_hat: (T,) denoised 시계열
    """
    z = np.asarray(z, dtype=float)
    T = z.shape[0]
    if T == 0:
        return z.copy()

    # r 추정 (없을 때): var(diff)/2 (백색가우시안 노이즈 가정)
    if r is None:
        if T >= 2:
            dz = np.diff(z)
            r_est = np.var(dz, ddof=1) / 2.0
        else:
            r_est = 1.0
        r = float(max(r_est, 1e-12))

    # q 설정
    if q is None:
        q = float(max(q_factor * r, 1e-12))

    # 초기값
    x_hat = np.empty(T, dtype=float)
    x = z[0] if init_x is None else float(init_x)
    P = (r if init_P is None else float(init_P))

    # 반복
    for t in range(T):
        # 1) 예측
        x_pred = x          # random walk: F=1
        P_pred = P + q

        # 2) 갱신
        K = P_pred / (P_pred + r)         # H=1
        x = x_pred + K * (z[t] - x_pred)
        P = (1.0 - K) * P_pred

        x_hat[t] = x

    return x_hat


def kalman_denoise_matrix(
    X: np.ndarray,
    *,
    q: float | None = None,
    r: float | None = None,
    q_factor: float = 0.01,
    axis_time_first: bool = True,
) -> np.ndarray:
    """
    다채널 행렬에 칼만 필터를 열/행별로 적용.
    - axis_time_first=True: X.shape=(T, Ns)  → 각 열을 1D로 처리
    - axis_time_first=False: X.shape=(Ns, T) → 각 행을 1D로 처리

    Args:
        X: 입력 행렬 (2D ndarray)
        q, r: 전 채널 공통 분산. None이면 채널별 자동(r) 추정, q=q_factor*r
        q_factor: q가 None일 때 q = q_factor * r
        axis_time_first: 시간축이 앞(T, Ns)인지 여부

    Returns:
        Y: 동일 shape의 denoised 행렬
    """
    X = np.asarray(X, dtype=float)
    if X.ndim != 2:
        raise ValueError(f"Expected 2D array, got {X.shape}")

    if axis_time_first:
        T, Ns = X.shape
        Y = np.empty_like(X)
        for k in range(Ns):
            r_k = r  # 공통 r 사용 또는 None이면 채널별 추정
            q_k = q
            Y[:, k] = kalman_denoise_1d(X[:, k], q=q_k, r=r_k, q_factor=q_factor)
        return Y
    else:
        Ns, T = X.shape
        Y = np.empty_like(X)
        for k in range(Ns):
            r_k = r
            q_k = q
            Y[k, :] = kalman_denoise_1d(X[k, :], q=q_k, r=r_k, q_factor=q_factor)
        return Y
