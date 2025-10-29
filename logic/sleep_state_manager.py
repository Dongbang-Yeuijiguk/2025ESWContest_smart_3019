import time
import config

class SleepStateManager:
    """
    사용자의 수면 상태를 관리하고, 변경 시 DB에 직접 기록하는 상태 머신 클래스.
    'EMPTY', 'AWAKE', 'RESTING_ON_BED', 'PRE_SLEEP', 'SLEEPING' 다섯 가지 상태를 가집니다.
    """
    def __init__(self, user_id: str, writer):
        self.user_id = user_id
        self.writer = writer
        self.current_state = "AWAKE"
        # 초기 시작 시간은 0.0으로 설정 (첫 데이터 타임스탬프로 업데이트됨)
        self.state_start_time = 0.0
        
        self.pre_sleep_threshold = config.PRE_SLEEP_DURATION_THRESHOLD

        # '깨어남 확인'을 위한 카운터와 임계값
        self.wakeup_confirm_count = 0
        self.WAKEUP_CONFIRM_THRESHOLD = config.WAKEUP_CONFIRM_THRESHOLD

        print(f"[{self.user_id}] SleepStateManager initialized. Current state: {self.current_state}")
        print(f" -> Threshold of PRE_SLEEP_DURATION: {self.pre_sleep_threshold}초")
        print(f" -> Wakeup confirmation count set to: {self.WAKEUP_CONFIRM_THRESHOLD}")


    def update_status(self, data: dict, current_timestamp: float) -> str:
        """
        새로운 추론 데이터를 받아와 수면 상태를 업데이트하고, 현재 상태를 반환합니다.
        
        Args:
            data (dict): AI 모델 추론 결과.
            current_timestamp (float): 현재 데이터 청크의 시작 시간 (초 단위 숫자).
        
        Returns:
            str: 현재 수면 상태 문자열.
        """
        status = data.get("status")
        movement = data.get("movement")

        # --- 전역 규칙 (Global Rules) ---
        if status == "empty":
            self._change_state("EMPTY", current_timestamp)
            return self.current_state

        if self.current_state == "EMPTY" and status == "present":
            self._change_state("AWAKE", current_timestamp)

        # --- 일반 상태 변화 규칙 (status가 'present'일 때만 실행) ---
        if self.current_state == "AWAKE":
            if movement == "using_phone_in_bed":
                self._change_state("RESTING_ON_BED", current_timestamp)
            elif movement == "lie":
                self._change_state("PRE_SLEEP", current_timestamp)

        elif self.current_state == "RESTING_ON_BED":
            if movement in ["lie", "rustle"]:
                self._change_state("PRE_SLEEP", current_timestamp)
            elif movement not in ["using_phone_in_bed"]:
                self._change_state("AWAKE", current_timestamp)

        elif self.current_state == "PRE_SLEEP":
            if movement in ["lie", "rustle"]:
                # 데이터의 타임스탬프로 경과 시간 계산
                duration = current_timestamp - self.state_start_time
                if duration > self.pre_sleep_threshold:
                    self._change_state("SLEEPING", current_timestamp)
            elif movement == "using_phone_in_bed":
                self._change_state("RESTING_ON_BED", current_timestamp)
            else: 
                self._change_state("AWAKE", current_timestamp)
        
        elif self.current_state == "SLEEPING":
            # '깨어남' 디바운싱 로직
            if movement in ["stand", "walk"]:
                self.wakeup_confirm_count += 1
                if self.wakeup_confirm_count >= self.WAKEUP_CONFIRM_THRESHOLD:
                    self._change_state("AWAKE", current_timestamp)
            else:
                self.wakeup_confirm_count = 0
        
        return self.current_state

    def _change_state(self, new_state: str, current_timestamp: float):
        """상태를 변경하고, 데이터 타임스탬프를 기준으로 시작 시간을 기록합니다."""
        if self.current_state != new_state:
            print(f"[{self.user_id}] 💤 STATE CHANGED: {self.current_state} -> {new_state}")
            self.current_state = new_state
            
            # time.time() 대신 전달받은 데이터의 시간을 상태 시작 시간으로 기록
            self.state_start_time = current_timestamp
            
            # 상태 변경 시 깨어남 카운터 초기화
            self.wakeup_confirm_count = 0
            
            if self.writer:
                self.writer.write_state_change(self.user_id, new_state)