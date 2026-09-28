from pydantic import BaseModel, ConfigDict

class SavedCruiseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cruise_id: str
    sailing_id: str | None = None
