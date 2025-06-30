from pydantic import BaseModel, Field

class Incident(BaseModel):
    incident_id: str = Field(default="", description="Unique identifier for the incident")
    incident_location: str = Field(default="Unknown", description="Location of the incident")
    incident_type: str = Field(default="General", description="Type of incident")
    priority: str
    timestamp: str = Field(default="", description="Timestamp of the incident in ISO format")
    status: str = Field(default="Open", description="Current status of the incident")
    source: str
    original_message: str


class UpdateStatus(BaseModel):
    incident_id: str
    status: str