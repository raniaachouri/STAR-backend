# main.py (Swagger-only API)
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import io, os, random
import pandas as pd
import joblib

from processor_utils import (
    load_all_models,
    process_pdf_buffer,
    save_to_db,
    list_extractions,
    get_extraction_by_id,
)

# ---- Import the runtime predictor (inference-only) ----
from fraud_predict_runtime import predict_from_raw_minimal

app = FastAPI(
    title="Extraction from PDFs + Fraud Scoring API",
    description="OCR ➜ extraction ➜ fraud scoring. Use /docs to try endpoints.",
    version="1.0.0",
)

# CORS (dev-friendly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Load OCR/processor models once ----------------
processor, pix_model, ocr_model = load_all_models()

# ---------------- Load FRAUD bundle once ----------------
FRAUD_BUNDLE_PATH = "./models/fraud/fraude_minimal_bundle.joblib"
if not os.path.exists(FRAUD_BUNDLE_PATH):
    raise FileNotFoundError(f"Fraud bundle not found at {FRAUD_BUNDLE_PATH}")
fraud_bundle = joblib.load(FRAUD_BUNDLE_PATH)

# ---------------- Pydantic schema for raw scoring ----------------
class FraudRawPayload(BaseModel):
    # Only include fields your model understands (matching training headers)
    assure: Optional[str] = Field(None, description="Assuré")
    tiers: Optional[str] = None
    contrat: Optional[str] = None
    numero_dossier: Optional[str] = None
    expert: Optional[str] = None
    observation: Optional[str] = None
    date_examen: Optional[str] = Field(None, description="e.g. '2023-06-05' or '05/06/2023'")
    date_accident: Optional[str] = None
    marque: Optional[str] = None
    puissance: Optional[str] = None
    energie: Optional[str] = None
    couleur: Optional[str] = None
    date_1_mc: Optional[str] = Field(None, description="Date 1ère mise en circulation")
    numero_serie: Optional[str] = None
    total_mo_ttc: Optional[float] = None
    total_four_ht: Optional[float] = None
    total_net: Optional[float] = None

def _row_to_df_for_model(extraction: dict) -> pd.DataFrame:
    """
    Map dict -> DataFrame with the exact headers the model expects (French notebook headers).
    """
    row = {
        "Assuré": extraction.get("assure", ""),
        "Tiers": extraction.get("tiers", ""),
        "Contrat": extraction.get("contrat", ""),
        "N° Dossier": extraction.get("numero_dossier", ""),
        "Expert": extraction.get("expert", ""),
        "Observation": extraction.get("observation", ""),
        "Date d'examen": extraction.get("date_examen", ""),
        "Date d'accident": extraction.get("date_accident", ""),
        "Marque": extraction.get("marque", ""),
        "Puissance": extraction.get("puissance", ""),
        "Énergie": extraction.get("energie", ""),
        "Couleur": extraction.get("couleur", ""),
        "Date 1ère mise en circulation": extraction.get("date_1_mc", ""),
        "N° Série": extraction.get("numero_serie", ""),
        "Total M.O TTC": extraction.get("total_mo_ttc", None),
        "Total FOUR HT": extraction.get("total_four_ht", None),
        "Total Net": extraction.get("total_net", None),
    }
    return pd.DataFrame([row])

def _predict_for_row_dict(extraction: dict):
    df_one = _row_to_df_for_model(extraction)
    pred, _feats = predict_from_raw_minimal(df_one, fraud_bundle)
    return {
        "algo_if_score": float(pred["algo_if_score"].iloc[0]),
        "score_suspicion": float(pred["score_suspicion"].iloc[0]),
        "suspect_oui_non": str(pred["suspect_oui_non"].iloc[0]),
    }

# ==========================
# JSON APIs (Swagger-friendly)
# ==========================

@app.get("/api/extractions", summary="List all extractions")
def api_list_extractions():
    return list_extractions()

@app.get("/api/extractions/{id}", summary="Get one extraction by id")
def api_get_extraction(id: int):
    data = get_extraction_by_id(id)
    if not data:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return data

@app.post("/api/upload", summary="Upload one or more PDFs, extract and save to DB")
async def api_upload(files: List[UploadFile] = File(...)):
    processed, skipped = [], []
    for f in files:
        try:
            if not f.filename.lower().endswith(".pdf"):
                skipped.append({"name": f.filename, "reason": "Not a PDF"})
                continue
            buf = io.BytesIO(await f.read()); buf.seek(0)
            result = process_pdf_buffer(buf, processor, pix_model, ocr_model)
            new_id = save_to_db(result)
            # Return both the ID and the extraction result
            processed.append({
                "name": f.filename, 
                "id": new_id,
                "extraction_result": result  # Add the extraction result here
            })
        except Exception as e:
            skipped.append({"name": f.filename, "reason": str(e)})
    return {"processed": processed, "skipped": skipped}

# ---------- FRAUD endpoints ----------

@app.post("/api/predict/{id}", summary="Score fraud for one extraction by id")
def api_predict_one(id: int):
    data = get_extraction_by_id(id)
    if not data:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    try:
        pred = _predict_for_row_dict(data)
        return {"id": id, "prediction": pred}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

@app.post("/api/predict_all", summary="Score fraud for ALL extractions")
def api_predict_all():
    rows = list_extractions()
    out = []
    for r in rows:
        try:
            pred = _predict_for_row_dict(r)
            out.append({"id": r["id"], "prediction": pred})
        except Exception as e:
            out.append({"id": r.get("id"), "error": str(e)})
    return {"results": out}

@app.post("/api/predict_raw", summary="Score fraud for a RAW JSON payload (not in DB)")
def api_predict_raw(payload: FraudRawPayload):
    try:
        pred = _predict_for_row_dict(payload.dict(exclude_none=True))
        return {"prediction": pred}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

@app.get("/api/predict_random", summary="Pick a random extraction and score it")
def api_predict_random():
    rows = list_extractions()
    if not rows:
        return JSONResponse({"detail": "no data"}, status_code=404)
    rid = random.choice(rows)["id"]
    return api_predict_one(rid)