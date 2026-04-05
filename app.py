import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
DB_FILE = "break_logs.csv"
EMP_FILE = "employees.csv"
HR_PASSWORD = "admin123"  # Change this to your desired password

def get_logic_day():
    """Handles the 5 AM to 3 AM logic."""
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
st.set_page_config(page_title="Break Tracker", layout="centered")
st.title("🕒 Shop Break System")

# Initialize Data
employees = load_data(EMP_FILE, ["id", "name", "designation", "allowed_min"])
if employees.empty:
    # Default data for setup
    employees = pd.DataFrame([
        {"id": "101", "name": "Employee A", "designation": "Staff", "allowed_min": 30},
        {"id": "102", "name": "Employee B", "designation": "Senior", "allowed_min": 45}
    ])
    employees.to_csv(EMP_FILE, index=False)

logs = load_data(DB_FILE, ["id", "date", "out_time", "in_time"])

# --- EMPLOYEE SECTION ---
st.header("Employee Break Entry")
search_id = st.text_input("Enter your Employee ID to start:", key="emp_id_input")

if search_id:
    # Search for employee
    res = employees[employees['id'].astype(str) == str(search_id)]
    
    if not res.empty:
        emp = res.iloc[0]
        current_day = get_logic_day()
        
        st.success(f"Welcome, {emp['name']}!")
        st.info(f"Allowed Break: {emp['allowed_min']} minutes")
        
        # Check for active (unfinished) breaks
        # We look for rows where 'in_time' is empty for this employee today
        active_break = logs[(logs['id'].astype(str) == str(emp['id'])) & 
                            (logs['date'] == str(current_day)) & 
                            (logs['in_time'].isna())]

        col1, col2 = st.columns(2)

        if active_break.empty:
            with col1:
                if st.button("🚪 Start Break (OUT)", type="primary", use_container_width=True):
                    new_log = {
                        "id": emp['id'],
                        "date": str(current_day),
                        "out_time": datetime.now().strftime("%H:%M:%S"),
                        "in_time": None
                    }
                    logs = pd.concat([logs, pd.DataFrame([new_log])], ignore_index=True)
                    logs.to_csv(DB_FILE, index=False)
                    st.toast("Break started!")
                    st.rerun()
        else:
            with col2:
                st.warning("You are currently on break.")
                if st.button("✅ Return (IN)", type="primary", use_container_width=True):
                    # Find the specific open break and close it
                    idx = active_break.index[-1]
                    logs.at[idx, 'in_time'] = datetime.now().strftime("%H:%M:%S")
                    logs.to_csv(DB_FILE, index=False)
                    st.toast("Break ended. Welcome back!")
                    st.rerun()

        # Show today's total so far
        today_total = logs[(logs['id'].astype(str) == str(emp['id'])) & (logs['date'] == str(current_day))]
        if not today_total.empty:
            st.write("---")
            st.write("**Your breaks today:**")
            st.dataframe(today_total[['out_time', 'in_time']], hide_index=True)
    else:
        st.error("ID not found. Please contact HR.")

# --- HR SECTION (PASSWORD PROTECTED) ---
st.sidebar.markdown("---")
st.sidebar.header("HR Administration")
hr_pass_input = st.sidebar.text_input("Enter HR Password", type="password")

if hr_pass_input == HR_PASSWORD:
    st.sidebar.success("Access Granted")
    
    st.divider()
    st.header("📊 HR Monthly Report")
    
    col_m, col_y = st.columns(2)
    sel_month = col_m.selectbox("Month", range(1, 13), index=datetime.now().month-1)
    sel_year = col_y.number_input("Year", value=datetime.now().year)

    if not logs.empty:
        # 1. Prepare Data
        report_df = logs.copy()
        report_df['date_dt'] = pd.to_datetime(report_df['date'])
        
        # 2. Filter for selected month/year
        report_df = report_df[(report_df['date_dt'].dt.month == sel_month) & 
                              (report_df['date_dt'].dt.year == sel_year)]
        
        if not report_df.empty:
            # 3. Calculate Minutes
            def calc_diff(row):
                if pd.isna(row['in_time']) or pd.isna(row['out_time']): return 0
                fmt = "%H:%M:%S"
                t_out = datetime.strptime(row['out_time'], fmt)
                t_in = datetime.strptime(row['in_time'], fmt)
                return (t_in - t_out).total_seconds() / 60

            report_df['min_used'] = report_df.apply(calc_diff, axis=1)
            
            # 4. Group by ID and Date (Total daily break)
            daily = report_df.groupby(['id', 'date'])['min_used'].sum().reset_index()
            
            # 5. Merge with Employee Rules
            final = daily.merge(employees[['id', 'name', 'allowed_min']], on='id')
            
            # 6. Calculate Deductions (only if they went OVER their limit)
            final['extra_min'] = (final['min_used'] - final['allowed_min']).clip(lower=0)
            
            # Display
            st.dataframe(final.rename(columns={
                "date": "Date",
                "name": "Employee",
                "min_used": "Total Used",
                "allowed_min": "Daily Limit",
                "extra_min": "Extra (Deduct Salary)"
            }), use_container_width=True, hide_index=True)
            
            # CSV Download Button for HR
            csv = final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report as CSV", csv, "monthly_report.csv", "text/csv")
        else:
            st.info("No logs for the selected month.")
elif hr_pass_input:
    st.sidebar.error("Incorrect Password")
