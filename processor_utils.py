import io
import os
import cv2
import torch
import pytesseract
import numpy as np
from pdf2image import convert_from_bytes
from transformers import Pix2StructProcessor, Pix2StructForConditionalGeneration
from doctr.models import ocr_predictor

from utils_ocr import (
    extract_tiers_with_crop_and_filter,
    extract_chassis_or_serie,
    extract_contrat_general_regex,
    extract_n_dossier_under_contrat,
    extract_date_mise_en_circulation,
    extract_designations_doctr,
    clean_temp_images,
)

from insert_utils import save_extraction_to_db, fetch_all_extractions, fetch_extraction_by_id

# === Model loading from the internet (Hugging Face/Doctr) ===
def load_all_models(hf_cache_dir: str | None = None):
    """
    Downloads models from the internet on first run and caches them.
    - Pix2Struct from Hugging Face: google/pix2struct-docvqa-base
    - Doctr OCR: downloads its weights automatically when pretrained=True
    Optional: pass hf_cache_dir to control where HF caches the files.
    """
    import os
    import torch
    from transformers import Pix2StructProcessor, Pix2StructForConditionalGeneration
    from doctr.models import ocr_predictor

    # Optional: choose a custom cache location (kept OUT of your repo)
    if hf_cache_dir:
        os.environ["HF_HOME"] = hf_cache_dir
        os.environ["HUGGINGFACE_HUB_CACHE"] = hf_cache_dir
        os.environ["TRANSFORMERS_CACHE"] = hf_cache_dir

    # ⚠️ Remove any local-only overrides so Doctr can download as needed
    os.environ.pop("DOCTR_CACHE_DIR", None)

    print("⏳ Downloading Pix2Struct from Hugging Face (first run may take a while)...")
    repo_id = "google/pix2struct-docvqa-base"   # ✅ remplacé "large" par "base"

    # Use half precision on GPU to save memory; float32 on CPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    processor = Pix2StructProcessor.from_pretrained(repo_id)
    model = Pix2StructForConditionalGeneration.from_pretrained(
        repo_id,
        torch_dtype=dtype
    ).to(device)

    # Doctr OCR (downloads automatically to its cache on first call)
    print("⏳ Downloading Doctr OCR weights (first run only)...")
    ocr_model = ocr_predictor(pretrained=True)

    print(f"✅ Models ready. Device: {device}, dtype: {dtype}")
    return processor, model, ocr_model


def _parse_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", ".").replace("D", "").replace(" DT", "").replace("DT", "").strip())
    except Exception:
        return val

def process_pdf_buffer(buffer: io.BytesIO, processor, pix_model, ocr_model):
    # 1) Convert only the first page at 300 DPI (Colab parity)
    pages = convert_from_bytes(buffer.read(), first_page=1, last_page=1, dpi=300)
    image_pil = pages[0].convert("RGB")
    image_pil.save("page.png")

    # 2) Tesseract preprocessing
    image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)
    text = pytesseract.image_to_string(thresh, config="--psm 6")
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # 3) OCR fields via regex/crops
    ocr_result = {
        "tiers": extract_tiers_with_crop_and_filter(image_cv, data),
        "chassis": extract_chassis_or_serie(image_cv, data),
        "contrat": extract_contrat_general_regex(text),
        "n_dossier": extract_n_dossier_under_contrat(lines),
        "date_circulation": extract_date_mise_en_circulation(text),
    }

    # 4) Pix2Struct Q&A (same questions as Colab)
    questions = {
        "Assuré": "Who is the Assuré?",
        "Expert": "Who is the expert?",
        "Date d'examen": "What is the date of examination?",
        "Date d'accident": "What is the date of accident?",
        "Observation": "What is the observation?",
        "Marque": "What is the Marque of the vehicle?",
        "Puissance": "What is the Puissance of the vehicle?",
        "Énergie": "What is the Énergie?",
        "Couleur": "What is the Couleur of the vehicle?",
        "Total M.O TTC": "What is the Total M.O TTC?",
        "Total FOUR HT": "What is the Total FOUR HT?",
        "Total Net": "What is the Total Net to pay?"
    }

    field_data = {}
    for key, q in questions.items():
        inputs = processor(images=image_pil, text=q, return_tensors="pt").to(pix_model.device)
        output = pix_model.generate(**inputs, max_new_tokens=64)
        field_data[key] = processor.decode(output[0], skip_special_tokens=True)

    # 5) DESIGNATIONS via Doctr (use the already loaded ocr_model)
    try:
        designations, montants = extract_designations_doctr("page.png", ocr_model)
    except Exception:
        designations, montants = [], []

    # 6) Final nested structure (strict Colab parity)
    final_output = {
        "Informations Générales": {
            "Assuré": field_data.get("Assuré", ""),
            "Tiers": ocr_result.get("tiers", ""),
            "Contrat": ocr_result.get("contrat", ""),
            "N° Dossier": ocr_result.get("n_dossier", ""),
            "Expert": field_data.get("Expert", ""),
            "Observation": field_data.get("Observation", ""),
            "Date d'examen": field_data.get("Date d'examen", ""),
            "Date d'accident": field_data.get("Date d'accident", ""),
        },
        "Détails du Véhicule": {
            "Marque": field_data.get("Marque", ""),
            "Puissance": field_data.get("Puissance", ""),
            "Énergie": field_data.get("Énergie", ""),
            "Couleur": field_data.get("Couleur", ""),
            "Date 1ère mise en circulation": ocr_result.get("date_circulation", ""),
            "N° Série": ocr_result.get("chassis", ""),
        },
        "Réparations et Désignations": {
            "Désignations": designations,
            "Montants": [_parse_float(m) for m in montants],
            "Total M.O TTC": _parse_float(field_data.get("Total M.O TTC", "0")),
            "Total FOUR HT": _parse_float(field_data.get("Total FOUR HT", "0")),
            "Total Net": _parse_float(field_data.get("Total Net", "0")),
        },
    }

    clean_temp_images()
    return final_output

# === DB passthroughs ===
def save_to_db(result):
    return save_extraction_to_db(result)

def list_extractions():
    return fetch_all_extractions()

def get_extraction_by_id(id_):
    return fetch_extraction_by_id(id_)
