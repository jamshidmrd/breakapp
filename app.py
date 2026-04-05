import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# --- CONFIGURATION & UTILS ---
DB_FILE = "break_logs.csv"
EMP_FILE = "employees.csv"

def get_logic_day():
    """
    Handles the 5 AM to 3 AM logic. 
    If current time is between midnight and 5 AM, it counts as the previous day.
    """
    now = datetime.now()
    if now.hour < 5:
        return (now - timedelta(days=1)).date()
    return now.date()

def load_data(file, columns):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

# --- APP SETUP ---
st.set_page_config(page_title="Break Tracker", layout="wide")
st.title("🕒 Employee Break Management")

# Initialize DataFrames
employees = load_data(EMP_FILE, ["id", "name", "designation", "allowed_min"])
# Example data if file is empty
if employees.empty:
    employees = pd.DataFrame([
        {"id": "101", "name": "Alice", "designation": "Staff", "allowed_min": 30},
        {"id": "102", "name": "Bob", "designation": "Manager", "allowed_min": 60},
    ])
    employees.to_csv(EMP_FILE, index=False)

logs = load_data(DB_FILE, ["id", "date", "out_time", "in_time"])

# --- SIDEBAR: SEARCH & SELECT ---
st.sidebar.header("Employee Search")
search_id = st.sidebar.text_input("Enter Employee ID")

selected_emp = None
if search_id:
    res = employees[employees['id'].astype(str) == search_id]
    if not res.empty:
        selected_emp = res.iloc[0]
        st.sidebar.success(f"Selected: {selected_emp['name']} ({selected_emp['designation']})")
    else:
        st.sidebar.error("Employee not found")

# --- MAIN SECTION: RECORD BREAK ---
if selected_emp is not None:
    current_day = get_logic_day()
    st.subheader(f"Recording Break for {selected_emp['name']} - {current_day}")
    
    # Filter logs for this employee today
    today_logs = logs[(logs['id'].astype(str) == str(selected_emp['id'])) & (logs['date'] == str(current_day))]
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚪 Go to Break (OUT)"):
            new_log = {
                "id": selected_emp['id'],
                "date": str(current_day),
                "out_time": datetime.now().strftime("%H:%M:%S"),
                "in_time": None
            }
            logs = pd.concat([logs, pd.DataFrame([new_log])], ignore_index=True)
            logs.to_csv(DB_FILE, index=False)
            st.rerun()

    with col2:
        # Check if there is an active break (Out time exists but In time is empty)
        active_break = logs[(logs['id'].astype(str) == str(selected_emp['id'])) & (logs['in_time'].isna())]
        if not active_break.empty:
            if st.button("✅ Return from Break (IN)"):
                idx = active_break.index[-1]
                logs.at[idx, 'in_time'] = datetime.now().strftime("%H:%M:%S")
                logs.to_csv(DB_FILE, index=False)
                st.rerun()
        else:
            st.info("No active break found. Click 'Go to Break' first.")

    # Show Today's Timeline
    if not today_logs.empty:
        st.write("### Today's Breaks")
        st.table(today_logs[['out_time', 'in_time']])

---

# --- REPORTING SECTION ---
st.header("📊 Monthly Report")
report_month = st.selectbox("Select Month", options=[1,2,3,4,5,6,7,8,9,10,11,12], index=datetime.now().month-1)

if not logs.empty:
    # Process data for reporting
    report_df = logs.copy()
    report_df['date'] = pd.to_datetime(report_df['date'])
    report_df = report_df[report_df['date'].dt.month == report_month]
    
    # Calculate duration
    def calc_min(row):
        if pd.isna(row['in_time']) or pd.isna(row['out_time']):
            return 0
        fmt = "%H:%M:%S"
        # Handle 3 AM wrap-around logic for duration calculation
        t_out = datetime.strptime(row['out_time'], fmt)
        t_in = datetime.strptime(row['in_time'], fmt)
        diff = (t_in - t_out).total_seconds() / 60
        return diff if diff > 0 else 0

    report_df['duration_min'] = report_df.apply(calc_min, axis=1)
    
    # Group by employee and day
    daily_summary = report_df.groupby(['id', 'date'])['duration_min'].sum().reset_index()
    daily_summary = daily_summary.merge(employees[['id', 'name', 'allowed_min']], on='id')
    
    # Calculate Extra Minutes
    daily_summary['extra_minutes'] = (daily_summary['duration_min'] - daily_summary['allowed_min']).clip(lower=0)
    
    st.dataframe(daily_summary.rename(columns={
        "duration_min": "Total Break (Min)",
        "allowed_min": "Allowed (Min)",
        "extra_minutes": "Over Limit (Deductible)"
    }))
