# Fair Fare AI – Transparent Ride Pricing Model
INFO6105 Final Project

## Overview

Fair Fare AI is a machine-learning system designed to estimate fair taxi prices for New York City rides.
Using NYC Yellow Taxi Trip Data (2023) merged with Taxi Zone metadata and NOAA weather data, the model predicts a rational, transparent fare for any trip based on:
    1. pickup/dropoff locations
    2. time of day
    3. distance
    4. weather conditions
    5. traffic-related indicators

On top of the ML pipeline, we built a user-facing app design that simulates how ride-share apps calculate hidden surcharges, allowing riders to compare:
1. Fair Price – ML-derived from real taxi data
2. Model Price – a traditional pricing model baseline
3. Hidden Fee – difference between the two (possible surge/extra margin)

## Tech Used
- **Python**: data processing, modeling, FastAPI backend
- **FastAPI**: REST API for fare prediction
- **scikit-learn**: model training (Linear Regression, Random Forest, HistGBR)
- **Pandas / NumPy**: data prep and feature engineering
- **React + Vite**: frontend UI
- **Leaflet + OpenStreetMap**: interactive map and routing
- **NOAA GSOD + NYC TLC data**: datasets for weather and taxi trips

## How It Works (Simple Step-by-Step)
1. **Collect data**: NYC taxi trips + taxi zones + daily weather data.
2. **Clean & merge**: remove bad trips, match zones, attach weather by date.
3. **Feature engineering**: add time, distance, and context features.
4. **Train models**: Linear Regression, Random Forest, HistGBR.
5. **Serve predictions**: FastAPI loads models and scaler/encoder.
6. **UI interaction**: user selects pickup/dropoff, traffic, weather, car type.
7. **Prediction result**: API returns:
   - Fair taxi price (rule-based baseline)
   - Model base price (ML ensemble)
   - Hidden fee (difference between the two)
   - Final AI fare with surge

## Demo Steps
1. Start the backend:
   - `pip install -r requirements.txt`
   - `cd backend`
   - `uvicorn main:app --reload --port 8500`
2. Start the frontend:
   - `cd Frontend`
   - `npm install`
   - `npm run dev`
3. Open the app in the browser (usually `http://localhost:5173`).
4. Pick a **pickup** and **destination** (map or search).
5. Adjust **traffic**, **weather**, and **car type**.
6. Click **Get price details** and review:
   - Fair Taxi Price
   - Model Base Price
   - Hidden Fee
   - Final AI Fare

## Datasets Used:

1. NYC Yellow Taxi Trip Data (2023): [https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page][https://d37ci6vzurychx.cloudfront.net/trip-data]
2. NYC Taxi Zones: [https://catalog.data.gov/dataset/nyc-taxi-zones-131e4/resource/2dd4a8a3-bf0b-46d4-b11a-0b5ce833527c]
3. NOAA GSOD Weather Data - [https://www.ncei.noaa.gov/data/global-summary-of-the-day/archive/]

## Models Trained

We trained three regression models:
1. Linear Regression
2. Random Forest Regressor
3. Histogram-based Gradient Boosting Regressor (HistGBR)

Then we built an ensemble model that averages predictions from the three models.


## Project Structure
PROJECT DS/
│
├── Frontend/           # React front-end app (user interface)
│
├── backend/            # FastAPI backend (prediction + API endpoints)
│
├── models/             # Saved ML models / preprocessing artifacts
│
├── data/               # Local data samples 
│
├── notebooks/          # Jupyter notebooks for the full DS pipeline
│   ├── 01_data_cleaning.ipynb
│   ├── 02_merge_data.ipynb
│   ├── 03_visualization.ipynb
│   ├── 04_path_handling.ipynb
│   ├── 05_model_training.ipynb
│   ├── 06_linear_regression.ipynb
│   ├── 07_random_forest.ipynb
│   ├── 08_HistGBR.ipynb
│   ├── 09_model_comparison.ipynb
│   └── 10_hidden_pricing_detection.ipynb
│
├── output/             # Generated results (CSVs, PNG plots, reports)
│   ├── eda_visualizations/
│   ├── model_comparison/
│   └── ... (metrics, residual plots, feature importance, etc.)
│
├── outputs/            # (Optional) extra exported artifacts
│
├── package.json        #  dependencies
├── package-lock.json
└── README.md

## To run the project

### Backend (FastAPI)
1. Install Python dependencies:
   pip install -r requirements.txt
2. (Optional) Configure env:
   - `DEMO_MODE=1` to run without ML artifacts
   - `CORS_ORIGINS=http://localhost:5173`
3. Start API:
   cd backend
   uvicorn main:app --reload --port 8500

### Frontend (Vite)
1. Install dependencies:
   cd Frontend
   npm install
2. (Optional) Configure API base:
   - Create `Frontend/.env` with `VITE_API_BASE=http://localhost:8500`
3. Start app:
   npm run dev

### Notebooks (data pipeline)
Install extra notebook dependencies (optional):
  pip install -r requirements-notebooks.txt
