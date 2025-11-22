import streamlit as st
import pandas as pd
import numpy as np
import requests
import joblib
from datetime import datetime
import os
from streamlit_autorefresh import st_autorefresh
import altair as alt

# Streamlit page setup
st.set_page_config(page_title="Wheat Monitoring Dashboard", layout="wide")

# Sidebar settings
with st.sidebar:
    st.header("Settings")
    refresh_interval = st.number_input("Refresh interval (seconds)", min_value=5, value=15, step=5)
    show_history = st.checkbox("Show historical data", value=True)
    max_rows = st.number_input("Max rows to show", min_value=10, value=1000, step=10)
    chart_var = st.selectbox(
        "Select variable to display in chart",
        ["temperature", "humidity", "soil_moisture", "soil_temperature",
         "light_intensity", "Nitrogen", "Phosphorus", "Potassium"]
    )

# ThingSpeak config
CHANNEL_ID = ''  # add yours
READ_API_KEY = ''  # add yours

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

RESULTS_FILE = 'results.csv'
STRESS_LABELS = {0: "healthy", 1: "moderate", 2: "stressed"}
OPT_N, OPT_P, OPT_K = 13.0, 10.0, 8.0
OPT_LIGHT = 14000.0

# Load models and scalers
stress_model = joblib.load('stress_model.pkl')
irrigation_model = joblib.load('irrigation_model.pkl')
stress_scaler = joblib.load('stress_scaler.pkl')
irrigation_scaler = joblib.load('irrigation_scaler.pkl')

# Functions
def fetch_latest_data():
    url = f'https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=1'
    response = requests.get(url).json()
    latest_entry = response['feeds'][-1]

    input_values = []
    for key, ts_field in FIELDS.items():
        val = latest_entry.get(ts_field)
        input_values.append(float(val) if val and val != "null" else 0.0)

    timestamp = latest_entry.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    entry_id = latest_entry.get('entry_id', 0)
    return np.array(input_values).reshape(1, -1), timestamp, entry_id


def preprocess_stress(data):
    df = pd.DataFrame(data, columns=stress_scaler.feature_names_in_)
    return stress_scaler.transform(df)


def preprocess_irrigation(data):
    df = pd.DataFrame(data[:, :5], columns=irrigation_scaler.feature_names_in_)
    return irrigation_scaler.transform(df)


def predict(data):
    stress_X = preprocess_stress(data)
    irrigation_X = preprocess_irrigation(data)
    stress_pred_encoded = stress_model.predict(stress_X)[0]
    irrigation_pred = irrigation_model.predict(irrigation_X)[0]
    stress_pred = STRESS_LABELS.get(stress_pred_encoded, "unknown")
    return stress_pred, irrigation_pred


def compute_npk_addition(N, P, K):
    return max(0, OPT_N - N), max(0, OPT_P - P), max(0, OPT_K - K)


def compute_light_addition(light):
    return max(0, OPT_LIGHT - light)


def send_to_thingspeak(irrigation, stress, add_N, add_P, add_K, add_light):
    WRITE_API_KEY = ""  # add yours
    url = (
        f"https://api.thingspeak.com/update?"
        f"api_key={WRITE_API_KEY}"
        f"&field1={irrigation}"
        f"&field2={stress}"
        f"&field3={add_N}"
        f"&field4={add_P}"
        f"&field5={add_K}"
        f"&field6={add_light}"
    )
    try:
        requests.get(url, timeout=5)
    except Exception as e:
        print(f"ThingSpeak send error: {e}")


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

    send_to_thingspeak(irrigation_pred, stress_pred, add_N, add_P, add_K, add_light)


def load_history():
    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE, parse_dates=['timestamp'])
        return df
    return pd.DataFrame()

# Session state
if 'history_df' not in st.session_state:
    st.session_state.history_df = load_history()
if 'last_entry_id' not in st.session_state:
    st.session_state.last_entry_id = None

# Auto-refresh page
st_autorefresh(interval=refresh_interval * 1000, key="datarefresh")

# Fetch latest data
try:
    data, timestamp, entry_id = fetch_latest_data()
    if entry_id != st.session_state.last_entry_id:
        st.session_state.last_entry_id = entry_id

        stress_pred, irrigation_pred = predict(data)
        N, P, K, light = data[0, 5], data[0, 6], data[0, 7], data[0, 4]
        add_N, add_P, add_K = compute_npk_addition(N, P, K)
        add_light = compute_light_addition(light)

        save_results(timestamp, data, irrigation_pred, stress_pred, add_N, add_P, add_K, add_light)

        latest_row = {
            'timestamp': timestamp,
            'temperature': data[0, 0],
            'humidity': data[0, 1],
            'soil_moisture': data[0, 2],
            'soil_temperature': data[0, 3],
            'light_intensity': light,
            'Nitrogen': N,
            'Phosphorus': P,
            'Potassium': K,
            'irrigation_amount': irrigation_pred,
            'stress_level': stress_pred,
            'add_N': add_N,
            'add_P': add_P,
            'add_K': add_K,
            'add_light': add_light
        }

        st.session_state.history_df = pd.concat(
            [st.session_state.history_df, pd.DataFrame([latest_row])],
            ignore_index=True
        )

except Exception as e:
    st.error(f"Error fetching live data: {e}")

# Historical Data
if show_history and not st.session_state.history_df.empty:
    st.subheader("Historical Data")
    st.dataframe(st.session_state.history_df.tail(int(max_rows)))

# Chart view
if not st.session_state.history_df.empty:
    st.subheader("Field Over Time")
    df_chart = st.session_state.history_df[['timestamp', 'temperature', 'humidity', 'soil_moisture',
                                           'soil_temperature', 'light_intensity',
                                           'Nitrogen', 'Phosphorus', 'Potassium']].tail(int(max_rows))

    df_melt = df_chart.melt(
        id_vars='timestamp',
        value_vars=['temperature', 'humidity', 'soil_moisture',
                    'soil_temperature', 'light_intensity',
                    'Nitrogen', 'Phosphorus', 'Potassium'],
        var_name='variable', value_name='value'
    )

    selected_var = st.selectbox("Select variable for chart",
                                ['temperature', 'humidity', 'soil_moisture',
                                 'soil_temperature', 'light_intensity',
                                 'Nitrogen', 'Phosphorus', 'Potassium'])

    chart = alt.Chart(df_melt[df_melt['variable'] == selected_var]).mark_line().encode(
        x='timestamp:T',
        y='value:Q',
        color=alt.value('#1f77b4')
    ).properties(width=800, height=400)

    st.altair_chart(chart, use_container_width=True)

# Predictions & Decisions
if not st.session_state.history_df.empty:
    latest = st.session_state.history_df.tail(1).iloc[0]
    st.subheader("Predictions & Decisions")
    st.markdown(f"""
    <div style="font-size:22px; line-height:1.5;">
    <strong>Stress Level:</strong> {latest['stress_level']}<br>
    <strong>Irrigation Amount:</strong> {latest['irrigation_amount']:.2f}<br>
    <strong>Recommended Additions:</strong><br>
    Nitrogen: {latest['add_N']:.2f} | 
    Phosphorus: {latest['add_P']:.2f} | 
    Potassium: {latest['add_K']:.2f} | 
    Light: {latest['add_light']:.2f}
    </div>
    """, unsafe_allow_html=True)

# Latest Metrics
if not st.session_state.history_df.empty:
    latest = st.session_state.history_df.tail(1).iloc[0]
    st.subheader("Latest Metrics")
    st.markdown(f"""
    **Timestamp:** {latest['timestamp']}  
    **Temperature:** {latest['temperature']:.2f}  
    **Humidity:** {latest['humidity']:.2f}  
    **Soil Moisture:** {latest['soil_moisture']:.2f}  
    **Soil Temperature:** {latest['soil_temperature']:.2f}  
    **Light Intensity:** {latest['light_intensity']:.2f}  
    **NPK:** N={latest['Nitrogen']:.2f}, P={latest['Phosphorus']:.2f}, K={latest['Potassium']:.2f}
    """)
