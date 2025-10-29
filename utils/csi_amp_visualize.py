import numpy as np
import matplotlib.pyplot as plt

def plot_csi_amp_heatmap(Amp, title=None):
    """
    Amp: shape (N_time, 52)  # 선택된 서브캐리어(6..31, 33..58)의 진폭
    """
    # y축 라벨용 실제 서브캐리어 번호 (0-based)
    subcarriers = list(range(6, 32)) + list(range(33, 59))  # 길이 52

    # imshow는 (y, x) 순서이므로 전치해서 그림
    img = Amp.T  # (52, N_time)

    plt.figure(figsize=(7, 3.5))
    plt.imshow(img, aspect='auto', origin='lower')  # 색상은 기본값 사용
    cbar = plt.colorbar()
    cbar.set_label("Amplitude", rotation=90)

    # 축 라벨
    plt.xlabel("Time Index")
    plt.ylabel("Subcarrier")

    # 서브캐리어 눈금 몇 개만 예쁘게 표시
    yticks_pos = np.linspace(0, len(subcarriers)-1, 5).astype(int)
    plt.yticks(yticks_pos, [subcarriers[p] for p in yticks_pos])

    if title:
        plt.title(title)

    plt.tight_layout()
    plt.show()