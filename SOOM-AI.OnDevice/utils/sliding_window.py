# utils/sliding_window.py
import numpy as np
from collections import deque

class SlidingWindow:
    """
    실시간 데이터 스트림을 위한 슬라이딩 윈도우.
    데이터 청크를 받아 윈도우를 채우고, 윈도우가 가득 차면 데이터를 제공한 뒤
    일정 스텝만큼 슬라이드합니다.
    """
    def __init__(self, window_size: int, step_size: int):
        """
        Args:
            window_size (int): 추론에 사용할 데이터 포인트의 수.
            step_size (int): 윈도우를 이동시킬 데이터 포인트의 수.
        """
        if window_size < step_size:
            raise ValueError("window_size는 step_size보다 크거나 같아야 합니다.")
        
        self.window_size = window_size
        self.step_size = step_size
        
        # 데이터를 효율적으로 추가하고 제거하기 위해 deque 사용
        self.buffer = deque()
        self.current_size = 0

    def add_data(self, data_chunk: np.ndarray):
        """
        새로운 데이터 청크를 버퍼에 추가합니다.
        data_chunk는 (T, F) 형태의 2D 배열이어야 합니다.
        """
        # deque는 1차원 데이터만 받으므로 각 row를 튜플이나 리스트로 추가
        for row in data_chunk:
            self.buffer.append(row)
        
        self.current_size += len(data_chunk)
        
        # 버퍼가 너무 커지는 것을 방지 (예: window_size의 2배 이상)
        # 실제로는 get_window와 slide가 주기적으로 호출되므로 극단적인 경우는 적음
        max_buffer_len = self.window_size * 2 
        while self.current_size > max_buffer_len:
            self.buffer.popleft()
            self.current_size -= 1
            
    def is_ready(self) -> bool:
        """윈도우가 추론할 만큼 충분한 데이터를 가졌는지 확인합니다."""
        return self.current_size >= self.window_size

    def get_window(self) -> np.ndarray:
        """
        현재 버퍼에서 추론에 사용할 윈도우를 반환하고 슬라이드합니다.
        is_ready()가 True일 때만 호출해야 합니다.
        """
        if not self.is_ready():
            raise RuntimeError("윈도우가 아직 준비되지 않았습니다. is_ready()를 먼저 확인하세요.")
        
        # 현재 버퍼를 NumPy 배열로 변환
        full_buffer_np = np.array(self.buffer)
        
        # 최신 데이터 window_size 만큼을 잘라냄
        window_data = full_buffer_np[-self.window_size:]
        
        # 윈도우를 step_size 만큼 슬라이드
        for _ in range(self.step_size):
            if self.buffer:
                self.buffer.popleft()
        
        self.current_size -= self.step_size
        
        return window_data