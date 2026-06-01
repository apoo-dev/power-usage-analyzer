import streamlit as st
import serial
import time
import json
import pandas as pd
import random

# --- CEB TARIFF CALCULATION LOGIC ---
def calculate_ceb_bill(units):
    """Calculates the electricity bill based on the Sri Lankan step-tariff system."""
    if units <= 0:
        return 0.0
        
    if units <= 60:
        if units <= 30:
            energy_charge = units * 5.00
            fixed_charge = 80.00
        else:
            energy_charge = (30 * 5.00) + ((units - 30) * 9.00)
            fixed_charge = 210.00
    else:
        if units <= 90:
            energy_charge = (60 * 14.00) + ((units - 60) * 20.00)
            fixed_charge = 400.00
        elif units <= 120:
            energy_charge = (60 * 14.00) + (30 * 20.00) + ((units - 90) * 28.00)
            fixed_charge = 1000.00
        elif units <= 180:
            energy_charge = (60 * 14.00) + (30 * 20.00) + (30 * 28.00) + ((units - 120) * 44.00)
            fixed_charge = 1500.00
        else:
            energy_charge = (60 * 14.00) + (30 * 20.00) + (30 * 28.00) + (60 * 44.00) + ((units - 180) * 85.00)
            fixed_charge = 2100.00
            
    return energy_charge + fixed_charge

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Watt-son Analyser", layout="wide")

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Watt-son Analyser", layout="wide")

# --- CUSTOM CSS INJECTION (The Glassmorphism Upgrade) ---
st.markdown("""
<style>
    /* 1. Dark, moody background gradient */
    .stApp {
        background-color: #0f172a; /* Deep Slate */
        background-image: radial-gradient(circle at 50% 0%, #1e293b 0%, #0f172a 70%);
        color: white;
    }

    /* 2. Hide the default Streamlit header and footer for a clean app look */
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* 3. Style the Metric Data Boxes as Frosted Glass */
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05); /* 5% white */
        border: 1px solid rgba(255, 255, 255, 0.1); /* Faint border */
        backdrop-filter: blur(12px); /* The "Glass" blur effect */
        -webkit-backdrop-filter: blur(12px);
        border-radius: 20px; /* Rounded corners */
        padding: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); /* Deep shadow */
        transition: transform 0.2s ease-in-out;
    }
    
    /* Slight hover effect on the glass cards */
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        background: rgba(255, 255, 255, 0.08);
    }

    /* 4. Style the Metric Text */
    div[data-testid="metric-container"] > label {
        color: #94a3b8 !important; /* Subtle gray for titles */
        font-weight: 600;
        font-size: 1.1rem;
    }
    div[data-testid="metric-container"] hdiv {
        color: #38bdf8 !important; /* Neon blue for the main numbers */
    }

    /* 5. Style the Expander (System Diagnostics) */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        color: white !important;
    }

    /* 6. Style the Dataframe/Table */
    [data-testid="stDataFrame"] {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 15px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ... (Continue with the rest of your normal Streamlit code below this) ...

# --- SESSION STATE INITIALIZATION (The Memory) ---
if 'device_config' not in st.session_state:
    st.session_state.device_config = pd.DataFrame({
        "Device Name": ["Device 1"],
        "Avg Hours/Day": [4.0]
    })

# UPDATED: Added power_sum and readings_count to track the true average
if 'device_stats' not in st.session_state:
    st.session_state.device_stats = {
        "Device 1": {"energy": 0.0, "power_sum": 0.0, "readings_count": 0, "current_power": 0.0}
    }

if 'last_arduino_e' not in st.session_state:
    st.session_state.last_arduino_e = 0.0

if 'sim_e' not in st.session_state:
    st.session_state.sim_e = 0.0

# --- SIDEBAR SETTINGS ---
st.sidebar.title("⚙️ System Settings")
arduino_port = st.sidebar.text_input("Arduino COM Port:", "COM6")
sim_mode = st.sidebar.checkbox("🛠️ Enable Simulation Mode")
st.sidebar.markdown("---")

# --- MAIN DASHBOARD LAYOUT ---
st.title("⚡ Smart Power Usage Analyser")

with st.expander("🔍 System Diagnostics: Raw USB Data Feed"):
    raw_data_display = st.empty()
st.markdown("---")

# 1. MOVED TO TOP: LIVE HARDWARE STATUS 
st.subheader("⚡ Live Hardware Status")
status_placeholder = st.empty()

# Electrical & Environmental Gauges
col1, col2, col3, col4, col5 = st.columns(5)
volt_metric = col1.empty()
curr_metric = col2.empty()
pwr_metric = col3.empty()
temp_metric = col4.empty()
hum_metric = col5.empty()

st.markdown("---")

# 2. DEVICE MANAGEMENT TABLE
st.subheader("🔌 Device Management")
st.info("Edit names and daily usage. Add new rows for new appliances at the bottom.")

# The Interactive Editor
edited_config = st.data_editor(st.session_state.device_config, num_rows="dynamic", hide_index=True, width="stretch")
st.session_state.device_config = edited_config

# Sync the background stats with the new table names
valid_devices = edited_config["Device Name"].dropna().tolist()
for dev in valid_devices:
    if dev not in st.session_state.device_stats:
        # Initialize new devices with zeroed-out average trackers
        st.session_state.device_stats[dev] = {"energy": 0.0, "power_sum": 0.0, "readings_count": 0, "current_power": 0.0}

# 3. ACTIVE DEVICE SELECTOR
st.subheader("🎛️ Active Connection")
active_device = st.selectbox("Which device is currently plugged into Watt-son?", valid_devices)
st.markdown("---")

# 4. LIVE DEVICE SUMMARY TABLE
st.subheader("📋 Live Device Summary")
summary_table_placeholder = st.empty()

st.markdown("---")

# 5. BOTTOM GRAPH
st.subheader("📈 Live Power Usage (Watts)")
chart_placeholder = st.empty()

# --- HARDWARE CONNECTION ---
ser = None
if not sim_mode:
    try:
        ser = serial.Serial(arduino_port, 9600, timeout=1)
    except Exception as e:
        st.sidebar.error(f"Cannot connect to {arduino_port}. Ensure the Arduino Serial Monitor is closed.")
        st.stop()

# --- REAL-TIME DATA LOOP ---
data_history = []

while True:
    try:
        # 1. GET DATA
        if sim_mode:
            is_safe = 1 if int(time.time()) % 15 < 12 else 0
            st.session_state.sim_e += 0.001 if is_safe else 0.0
            data = {
                "V": round(random.uniform(225.0, 235.0), 1),
                "I": round(random.uniform(1.5, 2.5), 2) if is_safe else 0.0,
                # Simulating a variable load that jumps around
                "P": round(random.uniform(100.0, 800.0), 1) if is_safe else 0.0, 
                "E": st.session_state.sim_e,
                "T": 29.5, "H": 62, "Safe": is_safe 
            }
            raw_data_display.code(json.dumps(data), language='json')
            time.sleep(1) 
        else:
            if ser.in_waiting > 0:
                raw_line = ser.readline()
                line = raw_line.decode('utf-8', errors='ignore').strip()
                raw_data_display.code(f"ARDUINO SAYS: {line}")
                data = json.loads(line)
            else:
                time.sleep(0.05)
                continue

        # 2. ENERGY ROUTING & AVERAGE MATH LOGIC
        current_arduino_e = data.get('E', 0)
        current_arduino_p = data.get('P', 0)
        
        # Calculate how much energy was used since the last loop
        delta_e = current_arduino_e - st.session_state.last_arduino_e
        if delta_e < 0: delta_e = current_arduino_e 
        st.session_state.last_arduino_e = current_arduino_e

        # Route data to the ACTIVE device and update the average math
        if active_device in st.session_state.device_stats:
            st.session_state.device_stats[active_device]['energy'] += delta_e
            st.session_state.device_stats[active_device]['current_power'] = current_arduino_p
            # Only add to the average if the device is actually drawing power (not just plugged in and off)
            if current_arduino_p > 0:
                st.session_state.device_stats[active_device]['power_sum'] += current_arduino_p
                st.session_state.device_stats[active_device]['readings_count'] += 1

        # 3. REBUILD THE SUMMARY TABLE
        summary_data = []
        for idx, row in edited_config.iterrows():
            dev_name = row["Device Name"]
            if pd.isna(dev_name) or dev_name not in st.session_state.device_stats: 
                continue
            
            hrs = float(row["Avg Hours/Day"])
            stats = st.session_state.device_stats[dev_name]
            
            live_pwr = stats['current_power'] if dev_name == active_device else 0.0
            used_energy = stats['energy']
            
            # THE TRUE AVERAGE MATH
            avg_power = 0.0
            if stats['readings_count'] > 0:
                avg_power = stats['power_sum'] / stats['readings_count']
            
            # Predict the monthly bill based on the TRUE AVERAGE power
            est_monthly_kwh = (avg_power / 1000.0) * hrs * 30.0
            est_bill = calculate_ceb_bill(est_monthly_kwh)
            
            summary_data.append({
                "Device Name": dev_name,
                "Plugged-In Usage (kWh)": f"{used_energy:.4f}",
                "Live Power (W)": f"{live_pwr:.1f}",
                "True Avg Power (W)": f"{avg_power:.1f}", # Added to show the math working!
                "Hrs/Day": hrs,
                "Est. End of Month Bill": f"Rs. {est_bill:,.2f}"
            })
            
        summary_table_placeholder.table(pd.DataFrame(summary_data))

        # 4. UPDATE HARDWARE GAUGES (Now at the top!)
        if data.get("Safe", 1) == 1:
            status_placeholder.error("🚨 **SYSTEM TRIPPED** (Relay ENERGIZED - Obstacle Detected!) 🚨")
        else:
            status_placeholder.success("✅ **SYSTEM NORMAL** (Relay DE-ENERGIZED - Power is Flowing)")

        volt_metric.metric("Voltage", f"{data.get('V', 0)} V")
        curr_metric.metric("Current", f"{data.get('I', 0)} A")
        pwr_metric.metric("Live Power", f"{current_arduino_p} W")
        temp_metric.metric("Temperature", f"{data.get('T', 0)} °C")
        hum_metric.metric("Humidity", f"{data.get('H', 0)} %")

        # 5. UPDATE GRAPH
        data_history.append(current_arduino_p)
        if len(data_history) > 40: 
            data_history.pop(0) 
        
        chart_placeholder.line_chart(pd.DataFrame(data_history, columns=["Power (Watts)"]))

    except json.JSONDecodeError:
        pass 
    except Exception as e:
        time.sleep(1)