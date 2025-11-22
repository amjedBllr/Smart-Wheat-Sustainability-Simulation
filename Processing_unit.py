import requests
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import time
import os

# -----------------------------
# CONFIG: ThingSpeak info
# -----------------------------
CHANNEL_ID = '3123837'
READ_API_KEY = 'MGBD4FBJ3PLVO5CP'

FIELDS = {
    "temperature": "field1",
    "humidity": "field2",
    "soil_moisture": "field3",
    "soil_temperature": "field4",
    "light_intensity": "field5",
    "Nitrogen": "field6",
    "Phosphorus": "field7",
    "Potassium": "field8"
}

STRESS_LABELS = {0: "healthy", 1: "moderate", 2: "stressed"}
RESULTS_FILE = 'results.csv'

# -----------------------------
# Load models and scalers
# -----------------------------
stress_model = joblib.load('stress_model.pkl')
irrigation_model = joblib.load('irrigation_model.pkl')
stress_scaler = joblib.load('stress_scaler.pkl')
irrigation_scaler = joblib.load('irrigation_scaler.pkl')
label_encoder = joblib.load('label_encoder.pkl')  # optional if needed

# -----------------------------
# OPTIMAL TARGETS for wheat
# (Adjust units to your sensor setup!)
# -----------------------------
# From research: for wheat = ~ N @ 125 kg/ha, P2O5 @ 25 kg/ha, K2O @ 50 kg/ha. :contentReference[oaicite:0]{index=0}
OPT_N = 13.0    # target Nitrogen
OPT_P = 10.0     # target Phosphorus (as P2O5 equivalent)
OPT_K = 8.0     # target Potassium (as K2O equivalent)

# Light intensity target from indoor wheat experiments: study used 300/500/700/900 µmol/m²/s. :contentReference[oaicite:1]{index=1}
OPT_LIGHT = 14000.0   # assume target light intensity in same units as your sensor (µmol/m²/s) – adjust if needed

# -----------------------------
# Fetch latest sensor data
# -----------------------------
def fetch_latest_data():
    url = f'https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=1'
    response = requests.get(url).json()
    latest_entry = response['feeds'][-1]

    input_values = []
    for key, ts_field in FIELDS.items():
        val = latest_entry.get(ts_field)
        input_values.append(float(val) if (val is not None and val != "null") else 0.0)

    timestamp = latest_entry.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    entry_id = latest_entry.get('entry_id', 0)
    return np.array(input_values).reshape(1, -1), timestamp, entry_id

# -----------------------------
# Preprocess using saved scalers
# -----------------------------
def preprocess_stress(data):
    df = pd.DataFrame(data, columns=stress_scaler.feature_names_in_)
    return stress_scaler.transform(df)

def preprocess_irrigation(data):
    # Assumes irrigation model uses first 5 features (temperature, humidity, soil_moisture, soil_temperature, light_intensity)
    df = pd.DataFrame(data[:, :5], columns=irrigation_scaler.feature_names_in_)
    return irrigation_scaler.transform(df)

# -----------------------------
# Heuristic functions for NPK & Light additions
# -----------------------------
def compute_npk_addition(current_N, current_P, current_K):
    """
    Returns the amounts to add (N_add, P_add, K_add) such that each meets or approaches its target.
    If current >= target, addition = 0.
    Adapt units and scaling as needed.
    """
    add_N = max(0.0, OPT_N - current_N)
    add_P = max(0.0, OPT_P - current_P)
    add_K = max(0.0, OPT_K - current_K)
    return add_N, add_P, add_K

def compute_light_addition(current_light):
    """
    Returns amount of light to add (or additional LED exposure time/intensity)
    such that target is reached. If current >= target, addition = 0.
    Adapt units and scaling as needed.
    """
    add_light = max(0.0, OPT_LIGHT - current_light)
    return add_light

# -----------------------------
# Predict stress & irrigation based on AI models
# -----------------------------
def predict(data):
    stress_X = preprocess_stress(data)
    irrigation_X = preprocess_irrigation(data)

    stress_pred_encoded = stress_model.predict(stress_X)[0]
    irrigation_pred = irrigation_model.predict(irrigation_X)[0]

    stress_pred = STRESS_LABELS.get(stress_pred_encoded, "unknown")
    return stress_pred, irrigation_pred

# -----------------------------
# Save results
# -----------------------------
def save_results(timestamp, data, irrigation_pred, stress_pred, add_N, add_P, add_K, add_light):
    row = {
        'timestamp': timestamp,
        'temperature': data[0, 0],
        'humidity': data[0, 1],
        'soil_moisture': data[0, 2],
        'soil_temperature': data[0, 3],
        'light_intensity': data[0, 4],
        'Nitrogen': data[0, 5],
        'Phosphorus': data[0, 6],
        'Potassium': data[0, 7],
        'irrigation_amount': irrigation_pred,
        'stress_level': stress_pred,
        'add_N': add_N,
        'add_P': add_P,
        'add_K': add_K,
        'add_light': add_light
    }
    df = pd.DataFrame([row])
    if os.path.exists(RESULTS_FILE):
        df.to_csv(RESULTS_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(RESULTS_FILE, index=False)

# -----------------------------
# MAIN LOOP
# -----------------------------
if __name__ == "__main__":
    last_entry_id = None

    while True:
        try:
            data, timestamp, entry_id = fetch_latest_data()

            if entry_id != last_entry_id:
                last_entry_id = entry_id

                print(f"Fetched sensor data: {data.flatten()}")

                stress_pred, irrigation_pred = predict(data)
                print(f"Stress level prediction: {stress_pred}")
                print(f"Irrigation amount prediction: {irrigation_pred:.2f}")

                # Heuristic additions
                current_N = data[0, 5]
                current_P = data[0, 6]
                current_K = data[0, 7]
                current_light = data[0, 4]

                add_N, add_P, add_K = compute_npk_addition(current_N, current_P, current_K)
                add_light = compute_light_addition(current_light)

                print(f"To add – N: {add_N:.2f}, P: {add_P:.2f}, K: {add_K:.2f}, Light: {add_light:.2f}")

                save_results(timestamp, data, irrigation_pred, stress_pred, add_N, add_P, add_K, add_light)
                print(f"Saved results to {RESULTS_FILE}")

            else:
                print("No new entry yet, waiting...")

            time.sleep(15)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)
