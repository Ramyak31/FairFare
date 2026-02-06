# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import numpy as np
import pandas as pd
import uvicorn
import math
import os
import sklearn

# --------------------------------------------------------------------
# Paths to trained artifacts (relative to backend/ directory)
# --------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LINEAR_MODEL_PATH   = os.path.join(BASE_DIR, "..", "models", "linear_regression_model.pkl")
RF_MODEL_PATH       = os.path.join(BASE_DIR, "..", "models", "random_forest_model.pkl")
HIST_GBM_MODEL_PATH = os.path.join(BASE_DIR, "..", "models", "hist_gbm_model.pkl")

SCALER_PATH  = os.path.join(BASE_DIR, "..", "models", "scaler.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "..", "models", "encoder.pkl")


def _safe_load(path: str):
    """Try to load a model; if it fails, return None instead of crashing."""
    try:
        print(f"[INFO] Loading model: {path}")
        return joblib.load(path)
    except Exception as e:
        print(f"[WARN] Could not load {path}: {e}")
        return None


def _sklearn_version_of(obj):
    return getattr(obj, "__sklearn_version__", None)


# --------------------------------------------------------------------
# Load models + preprocessors once at startup
# --------------------------------------------------------------------
linear_model   = _safe_load(LINEAR_MODEL_PATH)
rf_model       = _safe_load(RF_MODEL_PATH)
hist_gbm_model = _safe_load(HIST_GBM_MODEL_PATH)

scaler  = _safe_load(SCALER_PATH)
encoder = _safe_load(ENCODER_PATH)

STRICT_SKLEARN = os.getenv("STRICT_SKLEARN", "0").strip() in {"1", "true", "True", "yes", "YES"}

_artifact_versions = {
    "linear_regression": _sklearn_version_of(linear_model),
    "random_forest": _sklearn_version_of(rf_model),
    "hist_gbm": _sklearn_version_of(hist_gbm_model),
    "scaler": _sklearn_version_of(scaler),
    "encoder": _sklearn_version_of(encoder),
}

_mismatched = {
    k: v for k, v in _artifact_versions.items()
    if v is not None and v != sklearn.__version__
}

if _mismatched:
    print(f"[WARN] sklearn version mismatch: runtime={sklearn.__version__} artifacts={_mismatched}")
    if STRICT_SKLEARN:
        raise RuntimeError(
            f"sklearn version mismatch: runtime={sklearn.__version__} artifacts={_mismatched}"
        )


def _require_artifacts():
    """Ensure required preprocessing artifacts are available before prediction."""
    if scaler is None:
        raise HTTPException(status_code=500, detail="Scaler not loaded. Check models/scaler.pkl.")
    if encoder is None:
        raise HTTPException(status_code=500, detail="Encoder not loaded. Check models/encoder.pkl.")
    if not hasattr(scaler, "feature_names_in_"):
        raise HTTPException(status_code=500, detail="Scaler missing feature_names_in_.")
    if not hasattr(encoder, "feature_names_in_"):
        raise HTTPException(status_code=500, detail="Encoder missing feature_names_in_.")


def _validate_request(req: "RideRequest"):
    if not (0 <= req.traffic_level <= 100):
        raise HTTPException(status_code=422, detail="traffic_level must be between 0 and 100.")
    if not (0 <= req.hour <= 23):
        raise HTTPException(status_code=422, detail="hour must be between 0 and 23.")
    if not (0 <= req.day_of_week <= 6):
        raise HTTPException(status_code=422, detail="day_of_week must be between 0 (Sunday) and 6.")


def _validate_model_features(model, df: pd.DataFrame, name: str):
    if model is None:
        return
    if hasattr(model, "feature_names_in_"):
        model_feats = list(model.feature_names_in_)
        if model_feats != list(df.columns):
            raise HTTPException(
                status_code=500,
                detail=f"{name} feature mismatch: model expects {len(model_feats)} features, "
                       f"but request has {len(df.columns)}.",
            )
    elif hasattr(model, "n_features_in_"):
        if model.n_features_in_ != df.shape[1]:
            raise HTTPException(
                status_code=500,
                detail=f"{name} feature mismatch: model expects {model.n_features_in_} features, "
                       f"but request has {df.shape[1]}.",
            )


def _demo_app_price(fair_price: float, car_type: str, weather: str) -> float:
    car_mult = {
        "Economy": 1.0,
        "Comfort": 1.2,
        "Premium": 1.6,
        "SUV": 1.4,
    }.get(car_type, 1.0)

    weather_mult = 1.0
    if weather in {"Rainy", "Snowy", "Foggy"}:
        weather_mult = 1.1

    return float(fair_price * car_mult * weather_mult)


def _safe_category(encoder_obj, col: str, value: str) -> str:
    """Map a categorical value to a known category to avoid unknown-category warnings."""
    if not hasattr(encoder_obj, "feature_names_in_") or not hasattr(encoder_obj, "categories_"):
        return value
    try:
        idx = list(encoder_obj.feature_names_in_).index(col)
        known = list(encoder_obj.categories_[idx])
        if value in known:
            return value
        if "Unknown" in known:
            return "Unknown"
        if "unknown" in known:
            return "unknown"
        return known[0] if known else value
    except Exception:
        return value

# --------------------------------------------------------------------
# FastAPI app + CORS
# --------------------------------------------------------------------
app = FastAPI(title="Fair Fare AI API")

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5174"
origins_env = os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS)
origins = [o.strip() for o in origins_env.split(",") if o.strip()]

DEMO_MODE = os.getenv("DEMO_MODE", "0").strip() in {"1", "true", "True", "yes", "YES"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------
# Request schema
# --------------------------------------------------------------------
class RideRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    distance_km: float
    traffic_level: float   # 0–100 slider from UI
    weather: str           # "Sunny", "Cloudy", "Rainy"
    car_type: str          # "Economy", "Comfort", "Premium", "SUV"
    hour: int              # 0–23
    day_of_week: int       # 0=Sunday .. 6=Saturday


# --------------------------------------------------------------------
# Helper: haversine distance
# --------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2) -> float:
    """
    Compute great-circle distance between two points (km).
    """
    R = 6371  # Earth radius (km)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# --------------------------------------------------------------------
# Helper: ensemble model prediction (APP / MODEL price)
# --------------------------------------------------------------------
def predict_app_price_ensemble(features_df: pd.DataFrame):
    """
    Run all available models on the same features and return:
      - ensemble_price: mean of all model predictions
      - component_prices: dict with each model's individual prediction
    """
    preds = []
    component_prices = {}

    if linear_model is not None:
        p = float(linear_model.predict(features_df)[0])
        preds.append(p)
        component_prices["linear_regression"] = p

    if rf_model is not None:
        p = float(rf_model.predict(features_df)[0])
        preds.append(p)
        component_prices["random_forest"] = p

    if hist_gbm_model is not None:
        p = float(hist_gbm_model.predict(features_df)[0])
        preds.append(p)
        component_prices["hist_gbm"] = p

    if not preds:
        # Fail-safe so API doesn't silently return nonsense
        raise RuntimeError("No ML models are loaded – cannot predict app price")

    ensemble_price = float(np.mean(preds))
    return ensemble_price, component_prices


# --------------------------------------------------------------------
# Helper: simple "fair taxi price" baseline
# --------------------------------------------------------------------
def compute_fair_taxi_price(distance_km: float, traffic_level: float) -> float:
    """
    Transparent rule-based baseline, approximated from NYC yellow taxi tariffs:
      - base fare: $3.00
      - per-km:    $2.00
      - mild traffic bump: up to +15% when congestion is high
    This is NOT the ML model; this is our 'fair' reference price.
    """

    base = 3.0
    per_km = 2.0

    distance_component = per_km * max(distance_km, 0.1)

    # convert 0–100 traffic slider to ~0–0.15 multiplier
    traffic_factor = 1.0 + 0.15 * (traffic_level / 100.0)

    fair_price = (base + distance_component) * traffic_factor
    return float(fair_price)


# --------------------------------------------------------------------
# Prediction endpoint
# --------------------------------------------------------------------
@app.post("/predict")
def predict(req: RideRequest):
    """
    Take a RideRequest, build feature vector, run all models,
    and return:
      - Fair taxi price (rule-based)
      - App/model price (3-model ensemble)
      - Hidden fee vs fair
      - Final AI fare with surge
    """

    # ------------------------------------------------
    # 1. Validate request + compute distance if not provided / <= 0
    # ------------------------------------------------
    _validate_request(req)
    if not DEMO_MODE:
        _require_artifacts()

    distance_km = req.distance_km
    if distance_km <= 0:
        distance_km = haversine(
            req.pickup_lat, req.pickup_lng,
            req.drop_lat, req.drop_lng
        )

    # 👈 UPDATED: convert to miles because model was trained on trip_distance in miles
    distance_miles = distance_km * 0.621371

    # ------------------------------------------------
    # 2. Feature engineering + ML prediction (skipped in DEMO_MODE)
    # ------------------------------------------------
    component_prices = {}
    if DEMO_MODE:
        app_base_price = _demo_app_price(
            compute_fair_taxi_price(distance_km, req.traffic_level),
            req.car_type,
            req.weather,
        )
    else:
        # Numeric features – must match scaler.feature_names_in_
        numeric_features = list(scaler.feature_names_in_)
        means = scaler.mean_

        numeric_row = {}
        for i, col in enumerate(numeric_features):
            if col == "trip_distance":
                numeric_row[col] = distance_miles
            elif col == "distance_km":
                numeric_row[col] = distance_km
            elif col in ["distance_squared", "trip_distance_squared"]:
                numeric_row[col] = distance_miles ** 2
            elif col == "hour":
                numeric_row[col] = req.hour
            elif col == "day_of_week":
                numeric_row[col] = (req.day_of_week - 1) % 7
            elif col in ["traffic_multiplier", "traffic_level", "traffic_congestion"]:
                numeric_row[col] = req.traffic_level
            else:
                numeric_row[col] = float(means[i])

        num_df_raw = pd.DataFrame([numeric_row])
        num_scaled = scaler.transform(num_df_raw[numeric_features])
        num_df = pd.DataFrame(num_scaled, columns=numeric_features)

        # Categorical features – must match encoder.feature_names_in_
        cat_cols = list(encoder.feature_names_in_)
        cat_row = {}
        for col in cat_cols:
            if col == "weather_condition":
                cat_row[col] = _safe_category(encoder, col, req.weather)
            elif col == "car_type":
                cat_row[col] = _safe_category(encoder, col, req.car_type)
            else:
                cat_row[col] = _safe_category(encoder, col, "Unknown")

        cat_df_raw = pd.DataFrame([cat_row])
        encoded = encoder.transform(cat_df_raw[cat_cols])
        encoded_feature_names = encoder.get_feature_names_out(cat_cols)
        cat_df = pd.DataFrame(
            encoded.toarray() if hasattr(encoded, "toarray") else encoded,
            columns=encoded_feature_names,
        )

        # Combine numeric + categorical in same order used at training
        feature_columns = numeric_features + list(encoded_feature_names)
        final_df = pd.concat([num_df, cat_df], axis=1)[feature_columns]

        # Validate model feature compatibility
        _validate_model_features(linear_model, final_df, "Linear Regression")
        _validate_model_features(rf_model, final_df, "Random Forest")
        _validate_model_features(hist_gbm_model, final_df, "HistGBM")

        # Predict APP/MODEL base price using ALL THREE models (ensemble)
        app_base_price, component_prices = predict_app_price_ensemble(final_df)

    # ------------------------------------------------
    # 6. Compute FAIR taxi price (rule-based baseline)
    # ------------------------------------------------
    fair_price = compute_fair_taxi_price(distance_km, req.traffic_level)

    # Hidden fee vs fair (positive = app is more expensive)
    hidden_fee_vs_fair = app_base_price - fair_price

    # ------------------------------------------------
    # 7. Simple surge logic on top of app/model price
    # ------------------------------------------------
    surge_multiplier = 1.0
    bad_weather = req.weather in ["Rainy", "Snowy", "Foggy"]

    if req.traffic_level > 60 or bad_weather:
        surge_multiplier = 1.30  # 30% surge
    elif req.traffic_level > 35:
        surge_multiplier = 1.15  # mild surge

    final_fare = app_base_price * surge_multiplier
    surge_fee = final_fare - app_base_price

    # ------------------------------------------------
    # 8. Build response JSON
    # ------------------------------------------------
    return {
        # Prices
        "fair_taxi_price": round(fair_price, 2),
        "model_base_price": round(app_base_price, 2),
        "hidden_fee_vs_fair": round(hidden_fee_vs_fair, 2),
        "final_ai_fare": round(final_fare, 2),
        "surge_multiplier": round(surge_multiplier, 2),
        "surge_fee": round(surge_fee, 2),

        # Model metadata (for debugging / UI explanations)
        "model_used": "demo_rule_based" if DEMO_MODE else "ensemble",
        "model_component_prices": {
            name: round(price, 2) for name, price in component_prices.items()
        },

        # Echo back inputs (nice for debugging & UI summaries)
        "inputs": {
            "pickup_lat": req.pickup_lat,
            "pickup_lng": req.pickup_lng,
            "drop_lat": req.drop_lat,
            "drop_lng": req.drop_lng,
            "distance_km": round(distance_km, 3),
            "traffic_level": req.traffic_level,
            "weather": req.weather,
            "car_type": req.car_type,
            "hour": req.hour,
            "day_of_week": req.day_of_week,
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "sklearn_version": sklearn.__version__,
        "artifact_sklearn_versions": _artifact_versions,
        "strict_sklearn": STRICT_SKLEARN,
        "models": {
            "linear_regression": linear_model is not None,
            "random_forest": rf_model is not None,
            "hist_gbm": hist_gbm_model is not None,
        },
        "artifacts": {
            "scaler": scaler is not None,
            "encoder": encoder is not None,
        },
    }


# --------------------------------------------------------------------
# Local run
# --------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8500, reload=True)
