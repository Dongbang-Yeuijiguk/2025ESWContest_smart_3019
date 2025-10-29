from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date


class SleepData(BaseModel):
    date: date
    total_sleep_duration_minutes : int
    sleep_start_time : datetime
    sleep_end_time : datetime
    sleep_score : float

    toss_and_turn_times: Optional[List[str]] = None
    bpm_per_10min: Optional[List[int]] = None
    bpm_average: Optional[float] = None
    bpm_max: Optional[int] = None
    bpm_min: Optional[int] = None

    model_config = {"arbitrary_types_allowed": True,
                    "from_attributes": True}
