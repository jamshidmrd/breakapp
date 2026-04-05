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
        try:
            return pd.read_csv(file)
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

# --- APP SETUP ---
st.set_page_config(page_title="Break Tracker", layout="wide")
st.title("🕒 Employee Break Management")

# Initialize DataFrames
employees = load_data(EMP_FILE, ["id", "name", "designation", "allowed_min"])

# Example data if file is empty - You can edit these directly in the CSV later
if employees.empty:
    employees = pd.DataFrame([
        {"id": "101", "name": "Employee A", "designation": "Staff", "allowed_min": 30},
        {"id": "102", "name": "Employee B", "designation": "Senior", "allowed_min": 45},
        {"id": "103", "name": "Employee C", "designation": "Manager", "allowed_min": 60},
    ])
    employees.to_csv(EMP_FILE, index=False)

logs = load_data(DB_FILE, ["id", "date", "out_time", "in_time"])

# --- SIDEBAR: SEARCH & SELECT ---
st.sidebar.header("Employee Search")
search_id = st.sidebar.text_input("Enter Employee ID")

selected_emp = None
if search_id:
    # Ensure ID comparison works by converting to string
    res = employees[employees['id'].astype(str) == str(search_id)]
    if not res.empty:
        selected_emp = res.iloc[0]
        st.sidebar.success(f"Selected: {selected_emp['name']}")
        st.sidebar.info(f"Designation: {selected_emp['designation']}\nAllowed: {selected_emp['allowed_min']} mins")
    else:
        st.sidebar.error("Employee not found")

# --- MAIN SECTION: RECORD BREAK ---
if selected_emp is not None:
    current_day = get_logic_day()
    st.subheader(f"Recording Break: {selected_emp['name']}")
    st.write(f"**Business Date:** {current_day}")
    
    # Filter logs for this employee today
    today_logs = logs[(logs['id'].astype(str) == str(selected_emp['id'])) & (logs['date'] == str(current_day))]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Only allow 'Out' if there are no open 'In' slots
        active_break = today_logs[today_logs['in_time'].isna()]
        if active_break.empty:
            if st.button("🚪 Start Break (OUT)", use_container_width=True):
                new_log = {
                    "id": selected_emp['id'],
                    "date": str(current_day),
                    "out_time": datetime.now().strftime("%H:%M:%S"),
                    "in_time": None
                }
                logs = pd.concat([logs, pd.DataFrame([new_log])], ignore_index=True)
                logs.to_csv(DB_FILE, index=False)
                st.rerun()
        else:
            st.warning("Currently on break...")

    with col2:
        if not active_break.empty:
            if st.button("✅ End Break (IN)", use_container_width=True):
                # Find the specific row in the main logs dataframe
                mask = (logs['id'].astype(str) == str(selected_emp['id'])) & (logs['date'] == str(current_day)) & (logs['in_time'].isna())
                logs.loc[mask, 'in_time'] = datetime.now().strftime("%H:%M:%S")
                logs.to_csv(DB_FILE, index=False)
                st.rerun()

    if not today_logs.empty:
        st.divider()
        st.write("### Today's Activity")
        st.table(today_logs[['out_time', 'in_time']])

st.divider()

# --- REPORTING SECTION ---
st.header("📊 Monthly Report")
col_m, col_y = st.columns(2)
report_month = col_m.selectbox("Month", range(1, 13), index=datetime.now().month-1)
report_year = col_y.number_input("Year", value=datetime.now().year)

if not logs.empty:
    # Prepare data for calculation
    report_df = logs.copy()
    report_df['date_dt'] = pd.to_datetime(report_df['date'])
    
    # Filter by month and year
    report_df = report_df[(report_df['date_dt'].dt.month == report_month) & (report_df['date_dt'].dt.year == report_year)]
    
    if not report_df.empty:
        def calc_min(row):
            if pd.isna(row['in_time']) or pd.isna(row['out_time']):
                return 0
            fmt = "%H:%M:%S"
            t_out = datetime.strptime(row['out_time'], fmt)
            t_in = datetime.strptime(row['in_time'], fmt)
            # Basic duration in minutes
            return (t_in - t_out).total_seconds() / 60

        report_df['duration_min'] = report_df.apply(calc_min, axis=1)
        
        # Group by employee and date to get daily totals
        daily_summary = report_df.groupby(['id', 'date'])['duration_min'].sum().reset_index()
        
        # Merge with employee details to get allowed_min
        daily_summary = daily_summary.merge(employees[['id', 'name', 'allowed_min']], on='id')
        
        # Calculate Extra Minutes
        daily_summary['extra_minutes'] = (daily_summary['duration_min'] - daily_summary['allowed_min']).clip(lower=0)
        
        # Clean up display
        display_df = daily_summary.rename(columns={
            "date": "Date",
            "name": "Employee",
            "duration_min": "Used (Min)",
            "allowed_min": "Limit (Min)",
            "extra_minutes": "Deduction (Min)"
        })
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No logs found for this period.")
