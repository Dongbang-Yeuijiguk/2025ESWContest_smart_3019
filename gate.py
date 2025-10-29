# gate.py
from threading import Event
import time

TTS_PLAYING = Event()
LAST_TTS_TS = 0.0       # 마지막으로 TTS를 건드린 시각
REFRACTORY_SEC = 0.6    # TTS 끝난 뒤 추가로 무시할 시간(에코/누화 컷)
