"""Pydantic request/response schemas — the API contract."""
from __future__ import annotations
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class LabPoint(BaseModel):
    measured_on: date
    egfr: float = Field(..., description="mL/min/1.73m^2")
    crcl: Optional[float] = Field(None, description="mL/min (Cockcroft-Gault)")


class DrugFlag(BaseModel):
    ingredient: str
    metric: Literal["eGFR", "CrCl", "level-guided"]
    value_used: Optional[float]
    cutoff: Optional[float]
    severity: Literal["none", "review", "urgent", "manual"]
    action: str
    reference: str


class RiskExplanation(BaseModel):
    feature: str
    contribution: float
    value: float


class PatientSummary(BaseModel):
    patient_id: int
    name: str
    age: int
    sex: Literal["M", "F"]
    weight_kg: float
    ckd_confirmed: int
    ckd_stage: str
    latest_egfr: float
    egfr_slope_per_year: float
    n_renal_drugs: int
    risk_score: float
    top_drug: Optional[str]
    breach: bool



class PatientDetail(PatientSummary):
    trajectory: list[LabPoint]
    drug_flags: list[DrugFlag]
    explanation: list[RiskExplanation]
    advisory: str

class DrugDetails(BaseModel):
    drug_list: list[str]

class AllDrug(BaseModel):
    subject_id: int
    starttime: str
    stoptime: str
    drug_type: str
    drug: str
    prod_strength: str
    dose_val_rx : str
    dose_unit_rx : str
    form_unit_disp : str
    doses_per_24_hrs: Optional[float]
