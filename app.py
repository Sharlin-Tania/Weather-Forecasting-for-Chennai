import streamlit as st 
import pandas as pd 
import joblib
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
st.set_page_config(page_title="Chennai Weather AI", page_icon="🌦️", layout="wide")

# --- LOAD MODELS ---
@st.cache_resource
def load_assets():
    try:
        temp_model = joblib.load('temp_model.pkl')
        rain_model = joblib.load('rain_model.pkl')
        features = joblib.load('features_list.pkl')
        return temp_model, rain_model, features
    except FileNotFoundError:
        return None, None, None

# --- NOTIFICATION LOGIC ---
def send_email(sender_email, app_password, receiver_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return str(e)

# --- CALCULATION LOGIC ---
def calculate_utci(temp, humidity, wind):
    return temp + 0.35 * humidity - 0.7 * wind

def commute_score(rain_prob, utci, wind):
    score = min(rain_prob * 0.4, 40)
    score += 30 if wind > 10 else 20 if wind > 6 else 10 if wind > 3 else 0
    score += 30 if utci > 36 else 20 if utci > 32 else 10 if utci > 28 else 0
    return min(int(score), 100)

# --- UI LAYOUT ---
st.title("🌦️ Chennai Weather AI Dashboard")
st.markdown("---")

temp_model, rain_model, features_list = load_assets()

if temp_model is None:
    st.error("⚠️ Model files not found. Ensure .pkl files are in the folder.")
else:
    # Sidebar Setup
    with st.sidebar:
        st.header("🌦️ Weather Inputs")
        h = st.slider("Humidity (%)", 0, 100, 75)
        r = st.number_input("Rainfall Today (mm)", 0.0, 500.0, 0.0)
        w = st.slider("Wind Speed (m/s)", 0.0, 20.0, 2.5)
        
        st.divider()
        predict_btn = st.button("🚀 Run AI Prediction", type="primary")

    # Main Visuals
   # Main Visuals
    col_map, col_info = st.columns([2, 1])
    with col_map:
        st.subheader("📍 Location")
        
        # 1. Let the user adjust the pin
        lat_input = st.number_input("Adjust Latitude", value=12.90, format="%.4f")
        lon_input = st.number_input("Adjust Longitude", value=80.10, format="%.4f")
        
        # 2. Update the map based on inputs
        interactive_loc = pd.DataFrame({'lat': [lat_input], 'lon': [lon_input]})
        st.map(interactive_loc, zoom=11, use_container_width=True)
        
    with col_info:
        st.info(f"**Targeting:** {lat_input}, {lon_input}")
        st.info("**Big Data Methodology:** Using Random Forest Regressors and Classifiers to predict thermal indices and precipitation risk.")

    # --- INITIALIZE SESSION STATE ---
if 'prediction_done' not in st.session_state:
    st.session_state.prediction_done = False
if 'results' not in st.session_state:
    st.session_state.results = {}

# Prediction Execution
if predict_btn:
    st.session_state.prediction_done = True
    
    today = datetime.date.today()
    month, day = today.month, today.day
    week = today.isocalendar()[1]

    # 1. Predict Temperature
    temp_input = pd.DataFrame([[h, r, w, month, day]], columns=["Humidity", "Rainfall", "WindSpeed", "Month", "Day"])
    pred_temp = temp_model.predict(temp_input)[0]

    # 2. Predict Rain
    rain_input = pd.DataFrame([[pred_temp, h, w, month, day, week]], columns=["Temperature", "Humidity", "WindSpeed", "Month", "Day", "WeekOfYear"])
    rain_prob = rain_model.predict_proba(rain_input)[0][1] * 100
    
    # 3. Risk Calculation
    utci_val = calculate_utci(pred_temp, h, w)
    risk = commute_score(rain_prob, utci_val, w)
    risk_label = "SEVERE" if risk > 80 else "HIGH" if risk > 60 else "MODERATE" if risk > 30 else "LOW"

    # Store results in session state so they don't disappear
    st.session_state.results = {
        "temp": pred_temp,
        "rain": rain_prob,
        "risk": risk,
        "label": risk_label,
        "date": today.strftime('%Y-%m-%d')
    }

# --- DISPLAY RESULTS (Outside the button block, using session state) ---
if st.session_state.prediction_done:
    res = st.session_state.results
    st.divider()
    st.subheader("🎯 Prediction Results")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Predicted Temp", f"{res['temp']:.1f}°C")
    m2.metric("Rain Chance", f"{res['rain']:.1f}%")
    m3.metric("Commute Risk", f"{res['risk']}/100")
    m4.metric("Risk Level", res['label'])

    if res['risk'] > 60:
        st.error(f"🚨 ALERT: {res['label']} risk detected for Chennai commutes.")
    else:
        st.success(f"✅ STATUS: {res['label']} risk. Safe to travel.")

    # --- NOTIFICATION SECTION ---
    st.divider()
    st.subheader("📩 Send Live Alert")
    
    c1, c2 = st.columns(2)
    with c1:
        sender_email = st.text_input("From (Sender Gmail)", placeholder="sender@gmail.com")
    with c2:
        dest_email = st.text_input("To (Recipient Email)", placeholder="receiver@example.com")
        
    if st.button("Send Forecast Update"):
        # YOUR 16-CHAR APP PASSWORD GOES HERE
        MY_HIDDEN_APP_PASSWORD = "app_password" 

        if not sender_email or not dest_email:
            st.warning("Please enter both sender and recipient emails.")
        else:
            report_body = f"""
            CHENNAI WEATHER AI UPDATE
            Date: {res['date']}
            ---------------------------
            - Predicted Temp: {res['temp']:.1f}C
            - Rain Probability: {res['rain']:.1f}%
            - Commute Risk: {res['risk']}/100 ({res['label']})
            
            System Generated Alert.
            """
            with st.spinner("Connecting to Gmail..."):
                result = send_email(sender_email, MY_HIDDEN_APP_PASSWORD, dest_email, "Chennai Weather Alert", report_body)
            
            if result is True:
                st.success(f"Notification sent successfully from {sender_email}!")
            else:
                st.error(f"Failed to send: {result}")