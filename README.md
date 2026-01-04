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
Open terminal and run the below comments
1. For starting front end:
    cd Frontend
    npm run dev
2. For starting back end:
    cd backend
    uvicorn main:app --reload --port 8500
