// frontend/src/axios/getFarePrediction.js
import axios from "axios";

const API_BASE = "http://localhost:8500";

export async function getFarePrediction(payload) {
  const res = await axios.post(`${API_BASE}/predict`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  return res.data;
}
