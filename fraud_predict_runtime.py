# fraud_predict_runtime.py
import numpy as np
import pandas as pd

def _to_date(s):
    if s is None or str(s).strip()=="":
        return pd.NaT
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def _to_num(x):
    if x is None: return np.nan
    import re
    s = str(x).replace(",", ".")
    s = re.sub(r"[^0-9\.\-]", "", s)
    try: return float(s)
    except: return np.nan

def build_features_numeric(new_df, bundle):
    C = bundle["columns_used"]
    out = new_df.copy()

    # dates
    out["date_accident"] = out[C["date_accident"]].apply(_to_date) if C["date_accident"] in out.columns else pd.NaT
    out["date_examen"]   = out[C["date_examen"]].apply(_to_date)   if C["date_examen"]   in out.columns else pd.NaT
    out["date_mec"]      = out[C["date_mec"]].apply(_to_date)      if C["date_mec"]      in out.columns else pd.NaT

    # delay (days)
    out["delai_acc_exam_j"] = (out["date_examen"] - out["date_accident"]).dt.days
    if "delai_accident_exam_j" in out.columns and "delai_acc_exam_j" not in out.columns:
        out["delai_acc_exam_j"] = out["delai_accident_exam_j"]

    # age (keep negatives)
    out["age_vehicule_ans"] = np.where(
        out["date_mec"].notna() & out["date_accident"].notna(),
        (out["date_accident"] - out["date_mec"]).dt.days/365.25,
        np.nan
    )
    out["rule_age_negatif"] = out["age_vehicule_ans"].apply(lambda a: 1 if pd.notna(a) and a<0 else 0)
    out["age_vehicule_ans_clean"] = out["age_vehicule_ans"]

    # amounts
    if C["mo"]   in out.columns: out[C["mo"]]   = out[C["mo"]].apply(_to_num)
    if C["four"] in out.columns: out[C["four"]] = out[C["four"]].apply(_to_num)
    if C["net"]  in out.columns: out[C["net"]]  = out[C["net"]].apply(_to_num)

    out["sum_mo_four"] = np.where(
        (C["mo"] in out.columns) & (C["four"] in out.columns),
        out.get(C["mo"], np.nan).fillna(0) + out.get(C["four"], np.nan).fillna(0),
        np.nan
    )
    out["ratio_net_mo_four"] = np.where(
        out["sum_mo_four"].notna() & (out["sum_mo_four"]!=0) & (C["net"] in out.columns),
        out[C["net"]]/out["sum_mo_four"], np.nan
    )

    # single-row defaults (no history available here)
    out["multi_sinistres_win"]    = 1.0
    out["dossier_total_lignes"]   = 1.0
    out["dossier_dates_uniques"]  = np.where(out["date_accident"].notna(), 1.0, 0.0)

    # rules
    out["rule_delai_accident_exam_gt_15j"] = out["delai_acc_exam_j"].apply(lambda x: 1 if pd.notna(x) and x>15 else 0)
    out["rule_age_vehicule_extreme"] = out["age_vehicule_ans"].apply(
        lambda a: 1 if (pd.notna(a) and ((a<30/365.25) or (a>20))) else 0
    )
    out["rule_montant_outlier"] = 0
    out["rule_ratio_incoherent"] = np.where(
        out["sum_mo_four"].notna() & (C["net"] in out.columns),
        (out[C["net"]]>1.5*out["sum_mo_four"]).astype(int), 0
    )
    out["rule_multi_sinistres_contrat"]   = 0
    out["rule_dossier_repete_dates_diff"] = 0
    out["net_z"] = 0.0

    need = bundle["num_feature_cols"]
    for c in need:
        if c not in out.columns: out[c]=np.nan
    return out[need]

def build_features_text(new_df, bundle):
    col_obs = bundle["columns_used"]["observation"]
    vec = bundle.get("vectorizer"); svd = bundle.get("svd")
    if col_obs is None or vec is None or svd is None or (col_obs not in new_df.columns):
        return None
    X_tfidf = vec.transform(new_df[col_obs].astype(str).fillna(""))
    return svd.transform(X_tfidf)

def predict_from_raw_minimal(new_raw_df, bundle):
    # numeric
    X_num = build_features_numeric(new_raw_df.copy(), bundle)
    X_num_proc = bundle["preproc_num"].transform(X_num)

    # text
    X_text = build_features_text(new_raw_df.copy(), bundle)
    X_all = np.hstack([X_num_proc, X_text]) if (X_text is not None and X_text.shape[0]==X_num_proc.shape[0]) else X_num_proc

    # anomaly scores
    if_score = -bundle["isolation_forest"].score_samples(X_all)
    if_rank  = pd.Series(if_score).rank(pct=True).values

    # text anomaly
    if X_text is not None:
        mu_t = X_text.mean(axis=0, keepdims=True)
        sd_t = X_text.std(axis=0, keepdims=True); sd_t[sd_t==0]=1.0
        Z = (X_text-mu_t)/sd_t
        text_raw = np.mean(np.abs(Z), axis=1)
        text_anom = pd.Series(text_raw).rank(pct=True).values
    else:
        text_anom = np.zeros(X_all.shape[0])

    # rule intensity
    rule_cols = bundle.get("rule_cols", [])
    if len(rule_cols)>0 and all(c in X_num.columns for c in rule_cols):
        rule_matrix = X_num[rule_cols].fillna(0).values
        rule_intensity = rule_matrix.sum(axis=1)/float(len(rule_cols))
    else:
        rule_intensity = np.zeros(X_all.shape[0])

    # weighted score
    W = bundle.get("weights", {"rules":0.60,"text":0.30,"algo":0.10})
    score_susp = W["rules"]*rule_intensity + W["text"]*text_anom + W["algo"]*if_rank

    # critical rule override
    crit = bundle.get("critical_rules", [])
    if len(crit)>0 and all(c in X_num.columns for c in crit):
        override = (X_num[crit].fillna(0).sum(axis=1)>0).astype(int).values
    else:
        override = np.zeros(X_all.shape[0], dtype=int)

    pred = pd.DataFrame({
        "algo_if_score": if_score,
        "score_suspicion": score_susp,
        "suspect_oui_non": np.where((score_susp>=bundle["threshold"]) | (override==1), "oui", "non")
    })
    return pred, X_num
