// frontend/src/components/SubComponent.jsx
import React, { useEffect, useState, useMemo } from "react";
import L from "leaflet";
import { getFarePrediction } from "../axios/getFarePrediction";

export default function SubComponent() {
  // ------------ Constant configs ------------
  const WEATHER_OPTIONS = [
    {
      condition: "Sunny",
      icon: "fa-sun",
      temp: "24°C • Feels like 25°C",
      hint: "Bright & dry - any car works great.",
      recommended: "Economy",
    },
    {
      condition: "Cloudy",
      icon: "fa-cloud-sun",
      temp: "18°C • Feels like 16°C",
      hint: "Mild conditions - Comfort if you prefer smoother ride.",
      recommended: "Comfort",
    },
    {
      condition: "Rainy",
      icon: "fa-cloud-rain",
      temp: "14°C • Feels like 12°C",
      hint: "Rainy - covered, larger cars (Comfort / SUV) recommended.",
      recommended: "SUV",
    },
  ];

  const CAR_TYPES = [
    { type: "Economy", icon: "fa-car-side", base: 8 },
    { type: "Comfort", icon: "fa-car-rear", base: 12 },
    { type: "Premium", icon: "fa-taxi", base: 18 },
    { type: "SUV", icon: "fa-truck-field", base: 20 },
  ];

  // Simple map of known locations → coordinates
  const LOCATION_COORDS = {
    "Times Square": { lat: 40.758, lng: -73.9855 },
    "Central Park": { lat: 40.7829, lng: -73.9654 },
    "JFK Airport": { lat: 40.6413, lng: -73.7781 },
    "LaGuardia Airport": { lat: 40.7769, lng: -73.874 },
    "Brooklyn Bridge": { lat: 40.7061, lng: -73.9969 },
  };

  // ------------ State ------------
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [traffic, setTraffic] = useState(20); // 0–100
  const [selectedCar, setSelectedCar] = useState("Economy");
  const [selectedWeather, setSelectedWeather] = useState("Sunny");
  const [favorites, setFavorites] = useState([]);

  const [pickupCoords, setPickupCoords] = useState(null);   // { lat, lng }
  const [dropoffCoords, setDropoffCoords] = useState(null); // { lat, lng }
  const [mapSelectionMode, setMapSelectionMode] = useState(null); // 'pickup' | 'dropoff' | null

  const [showEstimate, setShowEstimate] = useState(false);

  const [apiLoading, setApiLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  // backend values
  const [backendFairPrice, setBackendFairPrice] = useState(null);
  const [backendModelPrice, setBackendModelPrice] = useState(null);
  const [backendHiddenFee, setBackendHiddenFee] = useState(null);
  const [backendSurgeFee, setBackendSurgeFee] = useState(null);
  const [backendFinalFare, setBackendFinalFare] = useState(null);
  const [backendSurgeMultiplier, setBackendSurgeMultiplier] = useState(null);

  // ------------ Reverse geocoding helper ------------

  const haversineKm = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // km
    const toRad = (deg) => (deg * Math.PI) / 180;
  
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) *
        Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) ** 2;
  
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };
  
  const reverseGeocode = async (lat, lng) => {
    try {
      const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`;
      const res = await fetch(url, {
        headers: {
          "User-Agent": "FairFareStudentProject/1.0",
        },
      });
      if (!res.ok) throw new Error("Geocode failed");
      const data = await res.json();
      if (data && data.display_name) {
        return data.display_name;
      }
    } catch (e) {
      console.error("Reverse geocode error:", e);
    }
    // fallback: show coords text
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  };

  // ------------ Map init ------------
  useEffect(() => {
    const map = L.map("map", {
      zoomControl: false,
      attributionControl: false,
    }).setView([40.758, -73.9855], 12); // NYC

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);

    L.control
      .zoom({
        position: "bottomright",
      })
      .addTo(map);

    window.__fairfareMap = map;

    return () => {
      map.remove();
      delete window.__fairfareMap;
    };
  }, []);

  // ------------ Map click handler for "Set location on map" ------------
  useEffect(() => {
    const map = window.__fairfareMap;
    if (!map) return;

    const handleClick = async (e) => {
      if (!mapSelectionMode) return;
      const { lat, lng } = e.latlng;

      const label = await reverseGeocode(lat, lng);

      if (mapSelectionMode === "pickup") {
        setPickup(label);
        setPickupCoords({ lat, lng });

        if (window.__pickupMarker) {
          map.removeLayer(window.__pickupMarker);
        }
        window.__pickupMarker = L.marker([lat, lng]).addTo(map);
      } else if (mapSelectionMode === "dropoff") {
        setDropoff(label);
        setDropoffCoords({ lat, lng });

        if (window.__dropoffMarker) {
          map.removeLayer(window.__dropoffMarker);
        }
        window.__dropoffMarker = L.marker([lat, lng]).addTo(map);
      }

      setMapSelectionMode(null); // exit selection mode after one click
    };

    map.on("click", handleClick);
    return () => {
      map.off("click", handleClick);
    };
  }, [mapSelectionMode]);

  // ------------ Favorites (localStorage) ------------
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("fairfare_favs") || "[]");
      setFavorites(stored);
    } catch {
      setFavorites([]);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("fairfare_favs", JSON.stringify(favorites));
  }, [favorites]);

  const addFavorite = (type, value) => {
    if (!value.trim()) return;
    if (favorites.some((f) => f.type === type && f.label === value.trim()))
      return;
    setFavorites((prev) => [...prev, { type, label: value.trim() }]);
  };

  const handleFavoriteClick = (fav) => {
    if (fav.type === "pickup") {
      setPickup(fav.label);
      if (LOCATION_COORDS[fav.label]) {
        setPickupCoords(LOCATION_COORDS[fav.label]);
      }
    } else {
      setDropoff(fav.label);
      if (LOCATION_COORDS[fav.label]) {
        setDropoffCoords(LOCATION_COORDS[fav.label]);
      }
    }
  };

  // ------------ Traffic badge ------------
  const trafficBadge = useMemo(() => {
    const v = Number(traffic);
    if (v >= 67)
      return {
        label: "High",
        className: "badge high",
        icon: "fa-triangle-exclamation",
      };
    if (v >= 33)
      return {
        label: "Medium",
        className: "badge medium",
        icon: "fa-circle-half-stroke",
      };
    return { label: "Low", className: "badge low", icon: "fa-circle" };
  }, [traffic]);

  // ------------ Weather derived ------------
  const weather = useMemo(
    () =>
      WEATHER_OPTIONS.find((w) => w.condition === selectedWeather) ||
      WEATHER_OPTIONS[0],
    [selectedWeather]
  );

  // ------------ Simple front-end estimate (fallback) ------------
  const estimates = useMemo(() => {
    const baseDistance = 4.5;
    const congestionFactor = 1 + Number(traffic) / 150;
    const weatherMult = weather.condition === "Rainy" ? 1.1 : 1;

    let carMult = 1;
    if (selectedCar === "Comfort") carMult = 1.2;
    if (selectedCar === "Premium") carMult = 1.6;
    if (selectedCar === "SUV") carMult = 1.4;

    const distance = baseDistance * congestionFactor;
    const fare = 3 + distance * 1.8 * carMult * weatherMult;
    const eta = 8 + distance * 1.3 * congestionFactor;

    return {
      distance: distance.toFixed(1),
      fare: fare.toFixed(2),
      eta: Math.round(eta),
    };
  }, [traffic, selectedCar, weather]);

  // ------------ Current location ------------
  const handleUseLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation not supported.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;

        const label = await reverseGeocode(latitude, longitude);

        setPickup(label);
        setPickupCoords({ lat: latitude, lng: longitude });

        const map = window.__fairfareMap;
        if (map) {
          if (window.__pickupMarker) {
            map.removeLayer(window.__pickupMarker);
          }
          window.__pickupMarker = L.circleMarker([latitude, longitude], {
            radius: 6,
            color: "#22c55e",
          }).addTo(map);
          map.setView([latitude, longitude], 14);
        }
      },
      () => alert("Unable to get current location.")
    );
  };

  // ------------ Call backend: Get price details ------------
  const handleGetPriceDetails = async () => {
    if (!pickup.trim() || !dropoff.trim()) {
      alert("Please enter both pickup and destination.");
      return;
    }

    setApiLoading(true);
    setApiError("");
    setBackendFairPrice(null);
    setBackendModelPrice(null);
    setBackendHiddenFee(null);
    setBackendSurgeFee(null);
    setBackendFinalFare(null);
    setBackendSurgeMultiplier(null);
    setShowEstimate(false);

    // 1️⃣ Resolve coordinates based on user input
    const resolvedPickup = pickupCoords || LOCATION_COORDS[pickup] || null;
    const resolvedDropoff = dropoffCoords || LOCATION_COORDS[dropoff] || null;

    if (!resolvedPickup || !resolvedDropoff) {
      setApiLoading(false);
      alert(
        "Please choose pickup and destination either from suggestions, use Current location, or set them on the map."
      );
      return;
    }

    // 2️⃣ Build payload with dynamic coordinates

    const distanceKm = haversineKm(
      resolvedPickup.lat,
      resolvedPickup.lng,
      resolvedDropoff.lat,
      resolvedDropoff.lng
    );
    
    const payload = {
      pickup_lat: resolvedPickup.lat,
      pickup_lng: resolvedPickup.lng,
      drop_lat: resolvedDropoff.lat,
      drop_lng: resolvedDropoff.lng,
      distance_km: distanceKm, // let backend recompute with haversine
      traffic_level: Number(traffic),
      weather: weather.condition,
      car_type: selectedCar,
      hour: new Date().getHours(),
      day_of_week: new Date().getDay(),
    };

    try {
      const data = await getFarePrediction(payload);

      // 🔹 map new backend keys, but keep fallbacks for older responses
      const fairTaxi =
        data.fair_taxi_price ??
        data.fair_price ??
        null;

      const modelBase =
        data.model_base_price ??
        data.ensemble_price ??
        data.model_price ??
        data.base_fare ??
        null;

      const hiddenVsFair =
        data.hidden_fee_vs_fair ??
        data.hidden_fee ??
        (fairTaxi != null && modelBase != null
          ? modelBase - fairTaxi
          : null);

      const finalAi =
        data.final_ai_fare ??
        data.final_fare ??
        data.predicted_fare ??
        modelBase ??
        null;

      const surgeMult =
        data.surge_multiplier ??
        (finalAi != null && modelBase != null && modelBase !== 0
          ? finalAi / modelBase
          : 1.0);

      const surgeFee =
        data.surge_fee ??
        (finalAi != null && modelBase != null
          ? finalAi - modelBase
          : null);

      setBackendFairPrice(fairTaxi);
      setBackendModelPrice(modelBase);
      setBackendHiddenFee(hiddenVsFair);
      setBackendSurgeFee(surgeFee);
      setBackendFinalFare(finalAi);
      setBackendSurgeMultiplier(surgeMult);

      console.log("Backend response:", data);
    } catch (err) {
      console.error(err);
      setApiError("Could not get AI fare. Please try again.");
    } finally {
      setApiLoading(false);
      setShowEstimate(true);
    }

    // 3️⃣ Map route animation using same coords
    const map = window.__fairfareMap;
    if (map) {
      const coords = [
        [resolvedPickup.lat, resolvedPickup.lng],
        [resolvedDropoff.lat, resolvedDropoff.lng],
      ];
      if (window.__fairfareRoute) {
        map.removeLayer(window.__fairfareRoute);
      }
      window.__fairfareRoute = L.polyline(coords, {
        color: "#22c55e",
        weight: 4,
      }).addTo(map);
      map.fitBounds(window.__fairfareRoute.getBounds(), { padding: [80, 80] });
    }
  };



  // ------------ Render ------------
  return (
    <div id="app">
      <div id="map" />

      <div className="glass-panel">
        {/* Header */}
        <div className="panel-header">
          <div className="brand">
            <div className="brand-icon">
              <i className="fa-solid fa-taxi" />
            </div>
            <div className="brand-text">
              <span>Fair Fare</span>
              <span>Ride Booking</span>
            </div>
          </div>
          <div className="status-pill">
            <span className="status-dot" />
            Live traffic
          </div>
        </div>

        {/* Trip details */}
        <div className="section">
          <div className="section-header">
            <span>Trip details</span>
            <span className="icon">
              <i className="fa-solid fa-route" />
            </span>
          </div>

          <div className="field-group">
            {/* Pickup */}
            <div className="field-row">
              <div className="field-icon">
                <i className="fa-solid fa-circle-dot" />
              </div>
              <div className="field-body">
                <div className="field-label-row">
                  <span>Pickup</span>
                  <button
                    type="button"
                    className="favorite-btn"
                    onClick={() => addFavorite("pickup", pickup)}
                  >
                    <i className="fa-regular fa-star" /> Save
                  </button>
                </div>
                <input
                  className="field-input"
                  value={pickup}
                  placeholder="Where should we pick you up?"
                  onChange={(e) => {
                    const val = e.target.value;
                    setPickup(val);
                    if (LOCATION_COORDS[val]) {
                      setPickupCoords(LOCATION_COORDS[val]);
                    } else {
                      setPickupCoords(null);
                    }
                  }}
                  list="location-suggestions"
                />
              </div>
              <div className="field-actions">
                <button
                  type="button"
                  className="pill-btn"
                  onClick={handleUseLocation}
                >
                  <i className="fa-solid fa-location-crosshairs" /> Current
                </button>
                <button
                  type="button"
                  className="pill-btn"
                  onClick={() => setMapSelectionMode("pickup")}
                  style={{ marginTop: 4 }}
                >
                  <i className="fa-solid fa-map-pin" /> Set on map
                </button>
              </div>
            </div>

            {/* Dropoff */}
            <div className="field-row">
              <div className="field-icon">
                <i className="fa-solid fa-location-dot" />
              </div>
              <div className="field-body">
                <div className="field-label-row">
                  <span>Destination</span>
                  <button
                    type="button"
                    className="favorite-btn"
                    onClick={() => addFavorite("dropoff", dropoff)}
                  >
                    <i className="fa-regular fa-star" /> Save
                  </button>
                </div>
                <input
                  className="field-input"
                  value={dropoff}
                  placeholder="Where are you going?"
                  onChange={(e) => {
                    const val = e.target.value;
                    setDropoff(val);
                    if (LOCATION_COORDS[val]) {
                      setDropoffCoords(LOCATION_COORDS[val]);
                    } else {
                      setDropoffCoords(null);
                    }
                  }}
                  list="location-suggestions"
                />
              </div>
              <div className="field-actions">
                <button
                  type="button"
                  className="pill-btn"
                  onClick={() => setMapSelectionMode("dropoff")}
                >
                  <i className="fa-solid fa-map-pin" /> Set on map
                </button>
              </div>
            </div>
          </div>

          {/* simple suggestions */}
          <datalist id="location-suggestions">
            <option value="Times Square" />
            <option value="Central Park" />
            <option value="JFK Airport" />
            <option value="LaGuardia Airport" />
            <option value="Brooklyn Bridge" />
          </datalist>

          <div className="favorites">
            <span style={{ display: "block", marginBottom: 2 }}>Favorites:</span>
            <div id="favorites-container">
              {favorites.map((f, idx) => (
                <span
                  key={idx}
                  className="tag"
                  onClick={() => handleFavoriteClick(f)}
                >
                  <i className="fa-solid fa-star" />
                  {f.label}
                </span>
              ))}
              {favorites.length === 0 && (
                <span style={{ color: "#4b5563" }}>None yet</span>
              )}
            </div>
          </div>
        </div>

        {/* Context (traffic + weather) */}
        <div className="section">
          <div className="section-header">
            <span>Context</span>
            <span className="icon">
              <i className="fa-solid fa-gauge-high" />
            </span>
          </div>

          <div className="two-col">
            <div className="half">
              <div className="congestion-row">
                <span>Traffic congestion</span>
                <span className={trafficBadge.className}>
                  <i className={`fa-solid ${trafficBadge.icon}`} />
                  {trafficBadge.label}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={traffic}
                onChange={(e) => setTraffic(e.target.value)}
                className="traffic-slider"
              />
            </div>

            <div className="half">
              <span style={{ fontSize: 12 }}>Weather</span>
              {/* Weather dropdown */}
              <select
                className="field-input"
                value={selectedWeather}
                onChange={(e) => setSelectedWeather(e.target.value)}
                style={{ marginBottom: 8 }}
              >
                {WEATHER_OPTIONS.map((w) => (
                  <option key={w.condition} value={w.condition}>
                    {w.condition}
                  </option>
                ))}
              </select>

              <div className="weather-box">
                <div className="weather-icon">
                  <i className={`fa-solid ${weather.icon}`} />
                </div>
                <div className="weather-meta">
                  <span>{weather.condition}</span>
                  <span>{weather.temp}</span>
                </div>
              </div>
              <div className="weather-hint">{weather.hint}</div>
            </div>
          </div>
        </div>

        {/* Car selection */}
        <div className="section">
          <div className="section-header">
            <span>Choose your ride</span>
            <span className="icon">
              <i className="fa-solid fa-car-side" />
            </span>
          </div>

          <div className="card-grid">
            {CAR_TYPES.map((car) => (
              <div
                key={car.type}
                className={
                  "car-card" + (selectedCar === car.type ? " selected" : "")
                }
                onClick={() => setSelectedCar(car.type)}
              >
                <i className={`fa-solid ${car.icon}`} />
                <span>{car.type}</span>
                <span className="price">From ${car.base}</span>
              </div>
            ))}
          </div>

          <div className="car-recommendation">
            <i className="fa-solid fa-lightbulb" />
            Recommended: <strong>{weather.recommended}</strong> (based on
            weather & traffic)
          </div>
        </div>

        {/* Estimate + Get price details */}
        <div className="section">
          <div className="section-header">
            <span>Estimate</span>
            <span className="icon">
              <i className="fa-solid fa-wallet" />
            </span>
          </div>

          <div className="summary-row">
            {/* 👇 Only show these cards after "Get price details" */}
            {showEstimate && (
              <div className="summary-metrics">
                {/* Fair taxi price */}
                <div className="metric-pill">
                  <div className="metric-label">Fair taxi price</div>
                  <div className="metric-value">
                    {apiLoading
                      ? "…"
                      : backendFairPrice !== null
                      ? `$${backendFairPrice.toFixed(2)}`
                      : "-"}
                  </div>
                </div>

                {/* Model base price */}
                <div className="metric-pill">
                  <div className="metric-label">Model base price</div>
                  <div className="metric-value">
                    {apiLoading
                      ? "…"
                      : backendModelPrice !== null
                      ? `$${backendModelPrice.toFixed(2)}`
                      : `$${estimates.fare}`}
                  </div>
                </div>

                {/* Hidden fee vs fair */}
                <div className="metric-pill">
                  <div className="metric-label">Hidden fee (vs fair)</div>
                  <div className="metric-value">
                    {apiLoading
                      ? "…"
                      : backendHiddenFee !== null
                      ? `$${backendHiddenFee.toFixed(2)}`
                      : "-"}
                    {backendHiddenFee !== null && (
                      <div style={{ fontSize: 11, opacity: 0.8 }}>
                        {backendHiddenFee > 0
                          ? "App is above fair price"
                          : "App is at / below fair price"}
                      </div>
                    )}
                  </div>
                </div>

                {/* Final AI fare */}
                <div className="metric-pill">
                  <div className="metric-label">Final AI fare</div>
                  <div className="metric-value">
                    {apiLoading
                      ? "…"
                      : backendFinalFare !== null
                      ? `$${backendFinalFare.toFixed(2)}`
                      : `$${estimates.fare}`}
                    {backendSurgeFee !== null &&
                      backendSurgeMultiplier !== null && (
                        <div style={{ fontSize: 11, opacity: 0.8 }}>
                          {`Includes $${backendSurgeFee.toFixed(
                            2
                          )} surge (x${backendSurgeMultiplier.toFixed(
                            2
                          )})`}
                        </div>
                      )}
                  </div>
                </div>
              </div>
            )}

            <button
              type="button"
              className="book-btn"
              onClick={handleGetPriceDetails}
              disabled={apiLoading}
            >
              {apiLoading ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin" /> Getting price…
                </>
              ) : (
                <>
                  <i className="fa-solid fa-bolt" /> Get price details
                </>
              )}
            </button>
          </div>

          {apiError && (
            <div style={{ color: "#f87171", fontSize: 12, marginTop: 8 }}>
              {apiError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
