# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import numpy as np
import pandas as pd
import uvicorn
import math
import os

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


# --------------------------------------------------------------------
# Load models + preprocessors once at startup
# --------------------------------------------------------------------
linear_model   = _safe_load(LINEAR_MODEL_PATH)
rf_model       = _safe_load(RF_MODEL_PATH)
hist_gbm_model = _safe_load(HIST_GBM_MODEL_PATH)

scaler  = joblib.load(SCALER_PATH)
encoder = joblib.load(ENCODER_PATH)

# --------------------------------------------------------------------
# FastAPI app + CORS
# --------------------------------------------------------------------
app = FastAPI(title="Fair Fare AI API")

origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5174",
]

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
    # 1. Compute distance if not provided / <= 0
    # ------------------------------------------------
    distance_km = req.distance_km
    if distance_km <= 0:
        distance_km = haversine(
            req.pickup_lat, req.pickup_lng,
            req.drop_lat, req.drop_lng
        )

    # 👈 UPDATED: convert to miles because model was trained on trip_distance in miles
    distance_miles = distance_km * 0.621371

    # ------------------------------------------------
    # 2. Numeric features – must match scaler.feature_names_in_
    # ------------------------------------------------
    numeric_features = list(scaler.feature_names_in_)
    means = scaler.mean_

    numeric_row = {}
    for i, col in enumerate(numeric_features):
        # 👈 UPDATED: map the correct distance feature(s)
        if col == "trip_distance":
            # main distance feature used during training (miles)
            numeric_row[col] = distance_miles
        elif col == "distance_km":
            # in case you also kept a km feature in training
            numeric_row[col] = distance_km
        elif col in ["distance_squared", "trip_distance_squared"]:
            numeric_row[col] = distance_miles ** 2
        elif col == "hour":
            numeric_row[col] = req.hour
        elif col == "day_of_week":
            numeric_row[col] = req.day_of_week
        elif col in ["traffic_multiplier", "traffic_level", "traffic_congestion"]:
            numeric_row[col] = req.traffic_level
        else:
            # Any other numeric column: use training mean so shape matches
            numeric_row[col] = float(means[i])

    num_df_raw = pd.DataFrame([numeric_row])
    num_scaled = scaler.transform(num_df_raw[numeric_features])
    num_df = pd.DataFrame(num_scaled, columns=numeric_features)

    # ------------------------------------------------
    # 3. Categorical features – must match encoder.feature_names_in_
    # ------------------------------------------------
    cat_cols = list(encoder.feature_names_in_)  # original categorical columns

    cat_row = {}
    for col in cat_cols:
        if col == "weather_condition":
            cat_row[col] = req.weather
        elif col == "car_type":
            cat_row[col] = req.car_type
        else:
            cat_row[col] = "Unknown"  # fallback category

    cat_df_raw = pd.DataFrame([cat_row])

    encoded = encoder.transform(cat_df_raw[cat_cols])
    encoded_feature_names = encoder.get_feature_names_out(cat_cols)
    cat_df = pd.DataFrame(
        encoded.toarray() if hasattr(encoded, "toarray") else encoded,
        columns=encoded_feature_names,
    )

    # ------------------------------------------------
    # 4. Combine numeric + categorical in same order used at training
    # ------------------------------------------------
    feature_columns = numeric_features + list(encoded_feature_names)
    final_df = pd.concat([num_df, cat_df], axis=1)[feature_columns]

    # ------------------------------------------------
    # 5. Predict APP/MODEL base price using ALL THREE models (ensemble)
    # ------------------------------------------------
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
        "model_used": "ensemble",
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


# --------------------------------------------------------------------
# Local run
# --------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8500, reload=True)
