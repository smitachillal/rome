"""REST endpoints: patient list ranked by risk, and per-patient detail."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.db import SessionLocal, Patient, Drug, PrescriptionDrugs
from app.models.schemas import PatientSummary, PatientDetail ,DrugDetails, AllDrug
from app.services.scoring import summarise, detail
from sqlalchemy import select
from app.services.recommender import recommend
from app.services.forecast import forecast_patient
from app.services.interactions import check_all
from app.services.guidance import build_guidance
from app.services.medication_review import build_review
from app.services.medication_status_org import (summarise as summarise_medications,
                                            current_drugs, historical_drugs,
                                            concurrent_pairs, reference_date)

from app.services.potassium import rule_assessment, suggest_medicines, classify_k

from app.services.potassium_predictor import predict_for_patient, predictor_available

router = APIRouter(prefix="/api", tags=["patients"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/patients", response_model=list[PatientSummary])
def list_patients(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()
    rows = [summarise(p) for p in patients]
    rows.sort(key=lambda r: r["risk_score"], reverse=True)
    return rows


@router.get("/patients/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return detail(p)


@router.get("/drugs/{patient_id}", response_model=DrugDetails)
def get_drugsbypatient(patient_id: int, db: Session = Depends(get_db)):
    # d = db.get(Drug, patient_id)
    # d = db.scalars(
    #     select(Drug).where(Drug.patient_id == patient_id)
    # ).all()
    # if d is None:
    #      raise HTTPException(404, "Drugs not found")
    # return DrugDetails( drug_list=list(d) )

    drug_names = db.scalars(
        select(Drug.ingredient)
        .where(Drug.patient_id == patient_id)
    ).all()
    if not drug_names:
        raise HTTPException(
            status_code=404,
            detail="Drugs not found"
        )
    return DrugDetails(drug_list=list(drug_names))

@router.get("/alldrugs/{patient_id}", response_model=list[AllDrug])
def get_drugsbypatient(patient_id: int, db: Session = Depends(get_db)):
    drugs = db.scalars(
        select(PrescriptionDrugs)
        .where(PrescriptionDrugs.subject_id == patient_id)
    ).all()
    if not drugs:
        raise HTTPException(
            status_code=404,
            detail="Drugs not found"
        )
    return list(drugs)

# @router.get("/recommendations/{patient_id}")
# def getSuggestedMedicine(patient_id: int, db: Session = Depends(get_db)):
#     p = db.get(Patient, patient_id)
#     if p is None:
#         raise HTTPException(404, "Patient not found")
#     _bundle()
#     print( " medicine recommaned 0------" , recommend(p) )
#     return {"status": "ok"}

@router.get("/patients/{patient_id}/recommendations")
def get_recommendations(patient_id: int, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    labs = sorted(p.labs, key=lambda l: l.measured_on)
    if not labs:
        raise HTTPException(400, "Patient has no lab data")
    latest = labs[-1]
    diagnoses = [d.category for d in getattr(p, "diagnoses", [])]
    patient = {
        "age": p.age, "sex": 1 if p.sex == "F" else 0,
        "weight_kg": p.weight_kg or 70.0,
        "egfr": latest.egfr, "crcl": latest.crcl or latest.egfr,
        "aki_stage": max((l.aki_stage or 0) for l in labs),
        "ckd_stage": {"G1":1,"G2":2,"G3a":3,"G3b":4,"G4":5,"G5":5}.get(p.ckd_stage or "", 3),
        "diagnoses": diagnoses,
        "n_existing_drugs": len(p.drugs),
    }
    return recommend(patient)



@router.get("/patients/{patient_id}/forecast")
def get_forecast(patient_id: int, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    series = [(l.measured_on, l.egfr) for l in p.labs]
    return forecast_patient(series)



@router.get("/patients/{patient_id}/interactions")
def get_interactions(patient_id: int, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    drugs = [d.ingredient for d in p.drugs]
    return check_all(drugs)

@router.get("/patients/{patient_id}/guidance")
def get_guidance(patient_id: int, role: str = "pharmacist", db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    patient = {"current_drugs": [d.ingredient for d in p.drugs],
               "ckd_stage": p.ckd_stage}
    return build_guidance(patient, role)


@router.get("/patients/{patient_id}/review")
def get_medication_review(patient_id: int, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    hb = None
    try:
        from app.services.recommender import _bundle
        b = _bundle()
        hb = b.get("drug_features") if b else None
    except Exception:
        hb = None
    return build_review(p.labs, [d.ingredient for d in p.drugs], hb)



@router.get("/patients/{patient_id}/medications")
def get_medications(patient_id: int, db: Session = Depends(get_db)):
    """Medication timeline: one row per drug with start/end dates and status."""
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    rows = summarise_medications(p.drugs)
    return {
        "medications": rows,
        "current": current_drugs(p.drugs),
        "stopped": historical_drugs(p.drugs),
        "concurrent_pairs": [list(x) for x in concurrent_pairs(p.drugs)],
    }


@router.get("/patients/{patient_id}/potassium")
def get_potassium(patient_id: int, db: Session = Depends(get_db)):
    """Potassium panel: trajectory, band, contributing agents, and suggestions."""
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")

    labs = sorted([l for l in p.labs if l.potassium_mmol_l is not None],
                  key=lambda l: l.measured_on)
    as_of = reference_date(p.labs, p.drugs)
    current = current_drugs(p.drugs, as_of)          # only drugs taken NOW

    if not labs:
        return {"available": False, "reason": "No potassium readings for this patient.",
                "current_drugs": current}

    latest = labs[-1]
    k = latest.potassium_mmol_l
    egfr = latest.egfr
    assess = rule_assessment(k, current, egfr)
    suggestions = suggest_medicines(k, current, egfr)

    return {
        "available": True,
        "latest": {"potassium": k, "measured_on": latest.measured_on.isoformat(),
                   "egfr": egfr},
        "flag": assess["flag"], "label": assess["label"],
        "severity": assess["severity"], "detail": assess["detail"],
        "actions": assess["actions"],
        "agents": assess["agents"],
        "suggestions": suggestions,
        "trajectory": [{"date": l.measured_on.isoformat(),
                        "potassium": l.potassium_mmol_l,
                        "flag": l.k_flag or classify_k(l.potassium_mmol_l),
                        "egfr": l.egfr} for l in labs],
        "thresholds": {"severe_high": 6.0, "high": 5.5, "high_normal": 5.0,
                       "low": 3.5, "severe_low": 3.0},
    }


@router.get("/patients/{patient_id}/potassium/predict")
def get_potassium_prediction(patient_id: int, db: Session = Depends(get_db)):
    """ML prediction: probability the NEXT potassium reading breaches threshold."""
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return predict_for_patient(p)


@router.get("/health")
def health():
    return {"status": "ok"}
