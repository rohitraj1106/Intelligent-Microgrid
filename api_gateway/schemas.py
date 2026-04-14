from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class NodeTelemetry(BaseModel):
    soc_pct: float = Field(ge=0, le=100)
    voltage_v: Optional[float] = None
    power_solar_kw: Optional[float] = None
    power_load_kw: Optional[float] = None
    battery_power_kw: Optional[float] = None
    grid_import_kw: Optional[float] = None
    grid_export_kw: Optional[float] = None


class NodeOrchestratorState(BaseModel):
    fsm_state: Optional[str] = None
    strategy_status: Optional[str] = None
    verdict: Optional[str] = None
    reason: Optional[str] = None


class NodeStateIngestRequest(BaseModel):
    node_id: str
    city: str
    timestamp: str
    telemetry: NodeTelemetry
    orchestrator: NodeOrchestratorState


class NodeStateResponse(BaseModel):
    node_id: str
    city: str
    timestamp: str
    stale: bool
    telemetry: NodeTelemetry
    orchestrator: NodeOrchestratorState


class NodeHealthResponse(BaseModel):
    node_id: str
    city: str
    soc_pct: float
    solar_kw: float = 0.0
    load_kw: float = 0.0
    fsm_state: Optional[str] = None
    strategy_status: Optional[str] = None
    stale: bool
    timestamp: str


class CommandRequest(BaseModel):
    node_id: str
    action: Literal[
        "BUY",
        "SELL",
        "CHARGE",
        "DISCHARGE",
        "HOLD",
        "start_trading",
        "stop_trading",
        "reset_soc",
        "inject_fault",
    ]
    amount_kwh: Optional[float] = Field(default=None, ge=0)
    price_per_kwh: Optional[float] = Field(default=None, ge=0)
    target_soc_pct: Optional[float] = Field(default=None, ge=0, le=100)
    target: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    status: str
    node_id: str
    action: str
    published_topic: str
    note: str


class GenericJSONResponse(BaseModel):
    data: Dict[str, Any]


class GenericListJSONResponse(BaseModel):
    data: List[Dict[str, Any]]
