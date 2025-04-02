# app/models/telemetry.py
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class TelemetryEvent(BaseModel):
    anonymousId: str
    sessionId: str
    step: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    scriptVersion: Optional[str] = None
    osVersion: Optional[str] = None 
    osName: Optional[str] = None
    cpuArchitecture: Optional[str] = None
    memoryGB: Optional[float] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)

class TelemetryStats(BaseModel):
    total_sessions: int
    successful_installs: int
    success_rate: float
    installation_by_os: Dict[str, int]
    steps_status: Dict[str, Dict[str, int]]
    avg_install_time: float