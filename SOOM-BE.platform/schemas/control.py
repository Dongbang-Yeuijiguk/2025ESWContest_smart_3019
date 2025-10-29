from pydantic import BaseModel

from typing import Optional, Any


class DeviceControl(BaseModel):
    device_type : Optional[str]
    payload : Optional[Any]
