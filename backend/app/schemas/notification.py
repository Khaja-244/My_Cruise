from pydantic import BaseModel

class DeviceIn(BaseModel):
    fcm_token: str
    platform: str

class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    data: dict | None
    is_read: bool
    created_at: str
