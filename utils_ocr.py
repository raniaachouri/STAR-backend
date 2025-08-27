import re
import os
import cv2
import pytesseract
from doctr.io import DocumentFile

# === Date 1ère mise en circulation ===
def extract_date_mise_en_circulation(text: str) -> str:
    patterns = [
        r"Date\s*1[°eè]?\s*MC\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"Date\s+de\s+1[èe]re\s+mise\s+en\s+circulation\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return ""

# === Tiers (crop autour du mot "tiers") ===
def extract_tiers_with_crop_and_filter(image, data):
    for i in range(len(data['text'])):
        word = data['text'][i].strip().lower()
        if word == "tiers":
            try:
                conf = int(float(data['conf'][i]))
            except Exception:
                conf = 0
            if conf > 40:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                cropped = image[max(y-10, 0):y+h+20, max(x-30, 0):x+w+800]
                text = pytesseract.image_to_string(cropped, config='--psm 6')
                for line in text.split('\n'):
                    if "tiers" in line.lower():
                        after = re.split(r'\btiers\b\s*[:\-]?', line, flags=re.IGNORECASE)
                        if len(after) > 1:
                            return re.sub(r"^[^\w]*", "", after[1].strip())
    return ""

# === N° châssis / série ===
def extract_chassis_or_serie(image, data):
    keywords = ["n°", "no", "nº"]
    suffixes = ["chassis", "châssis", "serie", "série"]
    for i in range(len(data['text']) - 1):
        word1 = data['text'][i].strip().lower()
        word2 = data['text'][i+1].strip().lower()
        if word1 in keywords and word2 in suffixes:
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            cropped = image[max(y-10, 0):y+h+20, max(x-20, 0):x+w+700]
            text = pytesseract.image_to_string(cropped, config='--psm 6')
            for line in text.split('\n'):
                if any(k in line.lower() for k in suffixes):
                    after = re.split(r'(n[\u00b0ºo]?\s*(chassis|châssis|serie|série))\s*[:\-]?', line, flags=re.IGNORECASE)
                    if len(after) >= 4:
                        return re.sub(r"^[^\w]*", "", after[3].strip())
    return ""

# === Contrat (regex générique) ===
def extract_contrat_general_regex(text: str):
    m = re.search(r"Contrat\s*[:;>\-]?\s*([A-Z0-9]{5,})", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""

# === N° de dossier (sous/près de "Contrat" le plus souvent) ===
def extract_n_dossier_under_contrat(lines):
    for line in lines:
        if re.search(r'n[\u00b0ºo]?\s*dossier', line, flags=re.IGNORECASE):
            m = re.search(r'\b\d{6,}[-_/]\d{6,}\b', line)
            if m:
                return m.group(0)
            parts = re.findall(r'\d{5,}', line)
            if len(parts) >= 2:
                return parts[0] + "_" + parts[1]
            elif len(parts) == 1:
                return parts[0]
    return ""

# === Détection de la table DESIGNATION (Doctr fourni par l'appelant) ===
def extract_designations_doctr(image_path: str, ocr_model):
    """
    Utilise un ocr_model Doctr déjà chargé (et donc local via DOCTR_CACHE_DIR)
    pour trouver/cropper la table DESIGNATION puis Tesseract pour lire les lignes.
    """
    from doctr.io import DocumentFile

    doc = DocumentFile.from_images([image_path])
    result = ocr_model(doc)

    img_cv = cv2.imread(image_path)
    h, w, _ = img_cv.shape
    table_region = None

    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    if "DESIGNATION" in word.value.upper():
                        (x_min, y_min), _ = word.geometry
                        x, y = int(x_min * w), int(y_min * h)
                        table_region = img_cv[y:y+1300, max(0, x-30):min(w, x+1000)]
                        break

    if table_region is None:
        raise ValueError("❌ Table DESIGNATION non trouvée.")

    cv2.imwrite("cropped_table.png", table_region)
    gray = cv2.cvtColor(table_region, cv2.COLOR_BGR2GRAY)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 10)
    table_text = pytesseract.image_to_string(gray, config='--psm 6')

    lines = [line.strip() for line in table_text.split("\n") if line.strip()]
    designations, montants = [], []
    montant_pattern = re.compile(r"\d{1,4}(?:[\s.,]?\d{3})*(?:[.,]\d{2,3})")

    for line in lines:
        if "designation" in line.lower():
            continue
        nums = montant_pattern.findall(line)
        if nums:
            montant = nums[0].replace(" ", "").strip()
            designation = line.split(nums[0])[0].strip()
            designation = re.sub(r"^[\-\•\*]+", "", designation)
            designation = re.sub(r"[|{}\[\]]", "", designation).strip()
            designations.append(designation)
            montants.append(montant)

    return designations, montants

def clean_temp_images():
    for f in ["page.png", "cropped_table.png"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
