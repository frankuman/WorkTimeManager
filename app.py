from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from functools import wraps
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this for production

# ---------------------------
# Login Required Decorator
# ---------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------
# Database Initialization
# ---------------------------
def init_db():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    # Create users table.
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    password TEXT
                 )''')
    # Ensure an admin account exists.
    c.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                  ("admin", generate_password_hash("Inova20!0")))
    # Create time_logs table with user_id.
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs (
                    id INTEGER PRIMARY KEY, 
                    date TEXT, 
                    check_in TEXT, 
                    check_out TEXT, 
                    flex_time REAL DEFAULT 0,
                    user_id INTEGER
                 )''')
    # Create diary table with an extra column for end_time.
    c.execute('''CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY, 
                    time_log_id INTEGER, 
                    timestamp TEXT, 
                    end_time TEXT,
                    note TEXT,
                    user_id INTEGER,
                    FOREIGN KEY(time_log_id) REFERENCES time_logs(id)
                 )''')
    conn.commit()
    conn.close()

# ---------------------------
# Helper Functions for Time Calculations
# ---------------------------
def calculate_daily_and_weekly_flex(logs):
    """
    Groups all complete sessions by day.
    Each day's work minutes are summed and compared against an 8‑hour (480 minute) baseline.
    Returns dictionaries for daily totals, daily flex, weekly hours, weekly flex, and overall flex.
    """
    daily_totals = {}
    fmt = "%H:%M"
    
    for log in logs:
        date_str = log[1]
        if not log[2] or not log[3]:
            continue  # skip incomplete sessions
        try:
            check_in = datetime.strptime(log[2].strip(), fmt)
            check_out = datetime.strptime(log[3].strip(), fmt)
        except ValueError:
            continue
        if check_out < check_in:
            check_out += timedelta(days=1)
        duration = (check_out - check_in).total_seconds() / 60
        daily_totals[date_str] = daily_totals.get(date_str, 0) + duration

    daily_flex = {}
    weekly_hours = {}
    weekly_flex = {}
    total_flex = 0
    for date_str, minutes in daily_totals.items():
        flex = minutes - 480  # baseline: 8 hours per day
        daily_flex[date_str] = flex
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        week = dt.isocalendar()[1]
        weekly_hours[week] = weekly_hours.get(week, 0) + minutes
        weekly_flex[week] = weekly_flex.get(week, 0) + flex
        total_flex += flex

    return daily_totals, daily_flex, weekly_hours, weekly_flex, total_flex

def calculate_flex_time(date, check_in, lunch_out, lunch_in, check_out):
    """
    Calculates the raw session duration (in minutes) from check-in to check-out.
    No default lunch break is assumed.
    """
    fmt = "%H:%M"
    if not check_in or not check_out:
        return 0
    try:
        check_in_dt = datetime.strptime(check_in.strip(), fmt)
        check_out_dt = datetime.strptime(check_out.strip(), fmt)
    except ValueError:
        return 0
    if check_out_dt < check_in_dt:
        check_out_dt += timedelta(days=1)
    return (check_out_dt - check_in_dt).total_seconds() / 60

# ---------------------------
# Authentication Routes
# ---------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))
        conn = sqlite3.connect("time_manager.db")
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            flash("Username already exists.")
            conn.close()
            return redirect(url_for("register"))
        hashed_pw = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        conn.close()
        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = sqlite3.connect("time_manager.db")
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            flash("Logged in successfully!")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))

# ---------------------------
# Main App Routes (User-Specific)
# ---------------------------
@app.route("/")
@login_required
def index():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("SELECT * FROM time_logs WHERE user_id=? ORDER BY date DESC, check_in DESC", (session["user_id"],))
    logs = c.fetchall()
    
    daily_totals, daily_flex, weekly_hours, weekly_flex, total_flex = calculate_daily_and_weekly_flex(logs)
    
    c.execute("SELECT COUNT(*) FROM time_logs WHERE check_out IS NULL AND user_id=?", (session["user_id"],))
    is_checked_in = c.fetchone()[0] > 0
    
    # Query for diary entries (for the listing table, if needed)
    c.execute("SELECT id, time_log_id, timestamp, note, end_time FROM diary WHERE user_id=? ORDER BY timestamp", (session["user_id"],))
    diary_entries = c.fetchall()
    
    # Query for an active diary entry for today (if one exists).
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        SELECT d.id, d.timestamp, d.note 
        FROM diary d 
        JOIN time_logs t ON d.time_log_id = t.id 
        WHERE d.user_id=? AND t.date=? AND d.end_time IS NULL 
        ORDER BY d.timestamp DESC LIMIT 1
    """, (session["user_id"], today))
    active_diary = c.fetchone()
    
    logs_with_weeks = []
    for log in logs:
        try:
            week = datetime.strptime(log[1], "%Y-%m-%d").isocalendar()[1]
        except Exception:
            week = 0
        logs_with_weeks.append((log[0], log[1], log[2], log[3], log[4] if log[4] is not None else 0, week))
    conn.close()
    return render_template("index.html", 
                           logs=logs_with_weeks, 
                           daily_totals=daily_totals, 
                           daily_flex=daily_flex, 
                           weekly_hours=weekly_hours, 
                           weekly_flex=weekly_flex, 
                           total_flex=total_flex, 
                           is_checked_in=is_checked_in, 
                           diary_entries=diary_entries,
                           active_diary=active_diary,
                           username=session.get("username"))



@app.route("/toggle_check", methods=["POST"])
@login_required
def toggle_check():
    now = datetime.now().strftime("%H:%M")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("SELECT id, date, check_in FROM time_logs WHERE check_out IS NULL AND date=? AND user_id=?", (today, session["user_id"]))
    row = c.fetchone()
    if row:
        work_minutes = calculate_flex_time(row[1], row[2], None, None, now)
        c.execute("UPDATE time_logs SET check_out=?, flex_time=? WHERE id=?", (now, work_minutes, row[0]))
        flash("Checked out successfully!")
    else:
        c.execute("INSERT INTO time_logs (date, check_in, user_id) VALUES (?, ?, ?)", (today, now, session["user_id"]))
        flash("Checked in successfully!")
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/add_day", methods=["GET", "POST"])
@login_required
def add_day():
    if request.method == "POST":
        date = request.form["date"]
        check_in = request.form.get("check_in", "").strip()
        check_out = request.form.get("check_out", "").strip()
        if not check_in or not check_out:
            flash("Both check-in and check-out times are required.")
            return redirect(url_for("add_day"))
        work_minutes = calculate_flex_time(date, check_in, None, None, check_out)
        conn = sqlite3.connect("time_manager.db")
        c = conn.cursor()
        c.execute("INSERT INTO time_logs (date, check_in, check_out, flex_time, user_id) VALUES (?, ?, ?, ?, ?)",
                  (date, check_in, check_out, work_minutes, session["user_id"]))
        conn.commit()
        conn.close()
        flash("Entry added successfully!")
        return redirect(url_for("index"))
    return render_template("add_day.html")

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("DELETE FROM diary WHERE time_log_id=? AND user_id=?", (id, session["user_id"]))
    c.execute("DELETE FROM time_logs WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Entry deleted successfully!")
    return redirect(url_for("index"))

@app.route("/add_diary", methods=["POST"])
@login_required
def add_diary():
    now = datetime.now().strftime("%H:%M")
    date = datetime.now().strftime("%Y-%m-%d")
    note = request.form["note"]
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("SELECT id FROM time_logs WHERE date=? AND user_id=? ORDER BY check_in DESC LIMIT 1", (date, session["user_id"]))
    time_log_id = c.fetchone()
    if time_log_id:
        c.execute("INSERT INTO diary (time_log_id, timestamp, note, user_id) VALUES (?, ?, ?, ?)", 
                  (time_log_id[0], now, note, session["user_id"]))
        conn.commit()
        flash("Diary entry added!")
    else:
        flash("No time log found for today. Add a time entry first!")
    conn.close()
    return redirect(url_for("index"))

@app.route("/edit_diary/<int:id>", methods=["GET", "POST"])
@login_required
def edit_diary(id):
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    if request.method == "POST":
        timestamp = request.form["timestamp"]
        note = request.form["note"]
        c.execute("UPDATE diary SET timestamp=?, note=? WHERE id=? AND user_id=?", (timestamp, note, id, session["user_id"]))
        conn.commit()
        conn.close()
        flash("Diary entry updated!")
        return redirect(url_for("index"))
    c.execute("SELECT id, timestamp, note FROM diary WHERE id=? AND user_id=?", (id, session["user_id"]))
    entry = c.fetchone()
    conn.close()
    return render_template("edit_diary.html", entry=entry)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    if request.method == "POST":
        check_in = request.form.get("check_in", "").strip()
        check_out = request.form.get("check_out", "").strip()
        if not check_in or not check_out:
            flash("Both check-in and check-out times are required.")
            return redirect(url_for("edit", id=id))
        c.execute("SELECT date FROM time_logs WHERE id=? AND user_id=?", (id, session["user_id"]))
        date = c.fetchone()[0]
        work_minutes = calculate_flex_time(date, check_in, None, None, check_out)
        c.execute("UPDATE time_logs SET check_in=?, check_out=?, flex_time=? WHERE id=? AND user_id=?", 
                  (check_in, check_out, work_minutes, id, session["user_id"]))
        conn.commit()
        conn.close()
        flash("Entry updated successfully!")
        return redirect(url_for("index"))
    c.execute("SELECT * FROM time_logs WHERE id=? AND user_id=?", (id, session["user_id"]))
    log = c.fetchone()
    conn.close()
    return render_template("edit.html", log=log)

# ---------------------------
# Diary & Report Routes
# ---------------------------
@app.route("/diary")
@login_required
def diary():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("""
        SELECT d.id, t.date, d.timestamp, d.note 
        FROM diary d 
        JOIN time_logs t ON d.time_log_id = t.id 
        WHERE d.user_id=? 
        ORDER BY t.date DESC, d.timestamp DESC
    """, (session["user_id"],))
    entries = c.fetchall()
    conn.close()
    
    diary_by_date = {}
    for entry in entries:
        date_str = entry[1]
        diary_by_date.setdefault(date_str, []).append({
            "id": entry[0],
            "time": entry[2],
            "note": entry[3]
        })
    return render_template("diary.html", diary_by_date=diary_by_date)
@app.route("/diary/activate", methods=["POST"])
@login_required
def diary_activate():
    note = request.form.get("note", "").strip()
    if not note:
        flash("Please enter a note for activation.")
        return redirect(url_for("index"))
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    # Find today's time log for the user.
    c.execute("SELECT id FROM time_logs WHERE date=? AND user_id=? ORDER BY check_in DESC LIMIT 1", (today, session["user_id"]))
    row = c.fetchone()
    if not row:
        flash("No time log found for today. Please check in first.")
        conn.close()
        return redirect(url_for("index"))
    time_log_id = row[0]
    # Insert a new diary entry (active, so end_time remains NULL).
    c.execute("INSERT INTO diary (time_log_id, timestamp, note, user_id) VALUES (?, ?, ?, ?)",
              (time_log_id, now_time, note, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Diary activated!")
    return redirect(url_for("index"))

@app.route("/diary/deactivate", methods=["POST"])
@login_required
def diary_deactivate():
    now_time = datetime.now().strftime("%H:%M")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    # Find the active diary entry for today.
    c.execute("""
        SELECT d.id FROM diary d 
        JOIN time_logs t ON d.time_log_id = t.id 
        WHERE d.user_id=? AND t.date=? AND d.end_time IS NULL 
        ORDER BY d.timestamp DESC LIMIT 1
    """, (session["user_id"], today))
    row = c.fetchone()
    if not row:
        flash("No active diary entry found.")
        conn.close()
        return redirect(url_for("index"))
    diary_id = row[0]
    c.execute("UPDATE diary SET end_time=? WHERE id=?", (now_time, diary_id))
    conn.commit()
    conn.close()
    flash("Diary deactivated!")
    return redirect(url_for("index"))

@app.route("/diary_report")
@login_required
def diary_report():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("""
        SELECT t.date, d.timestamp, d.note 
        FROM diary d 
        JOIN time_logs t ON d.time_log_id = t.id 
        WHERE d.user_id=? 
        ORDER BY t.date ASC, d.timestamp ASC
    """, (session["user_id"],))
    diary_entries = c.fetchall()
    c.execute("""
        SELECT date, SUM(flex_time) as total_minutes 
        FROM time_logs 
        WHERE check_in IS NOT NULL AND check_out IS NOT NULL AND user_id=? 
        GROUP BY date
    """, (session["user_id"],))
    daily_data = c.fetchall()
    conn.close()
    
    daily_totals = {date: total_minutes for date, total_minutes in daily_data}
    
    diary_by_date = {}
    for date, timestamp, note in diary_entries:
        diary_by_date.setdefault(date, []).append({"time": timestamp, "note": note})
    
    weekly_report = {}
    monthly_report = {}
    for date_str, notes in diary_by_date.items():
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        week = dt.isocalendar()[1]
        month = dt.strftime("%Y-%m")
        
        if week not in weekly_report:
            weekly_report[week] = {"dates": {}, "total_minutes": 0}
        minutes = daily_totals.get(date_str, 0)
        weekly_report[week]["dates"][date_str] = {
            "notes": notes,
            "minutes": minutes
        }
        weekly_report[week]["total_minutes"] += minutes
        
        if month not in monthly_report:
            monthly_report[month] = {"dates": {}, "total_minutes": 0}
        monthly_report[month]["dates"][date_str] = {
            "notes": notes,
            "minutes": minutes
        }
        monthly_report[month]["total_minutes"] += minutes
    
    return render_template("diary_report.html", 
                           weekly_report=weekly_report, 
                           monthly_report=monthly_report)

# ---------------------------
# Summary Route (Optional)
# ---------------------------
@app.route("/summary")
@login_required
def summary():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("SELECT * FROM time_logs WHERE user_id=? ORDER BY date", (session["user_id"],))
    logs = c.fetchall()
    daily_totals, daily_flex, weekly_hours, weekly_flex, total_flex = calculate_daily_and_weekly_flex(logs)
    conn.close()
    return render_template("summary.html", 
                           daily_totals=daily_totals, 
                           daily_flex=daily_flex, 
                           weekly_hours=weekly_hours, 
                           weekly_flex=weekly_flex, 
                           total_flex=total_flex)

# ---------------------------
# ADMIN Routes
# ---------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("username", "").lower() != "admin":
            flash("Admins only.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin")
@login_required
@admin_required
def admin():
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("SELECT id, username FROM users ORDER BY username")
    users = c.fetchall()
    conn.close()
    return render_template("admin.html", users=users)

@app.route("/admin/reset_password/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_reset_password(user_id):
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        if not new_password:
            flash("Please enter a new password.")
            return redirect(url_for("admin_reset_password", user_id=user_id))
        hashed_pw = generate_password_hash(new_password)
        conn = sqlite3.connect("time_manager.db")
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, user_id))
        conn.commit()
        conn.close()
        flash("Password reset successfully!")
        return redirect(url_for("admin"))
    return render_template("admin_reset_password.html", user_id=user_id)

@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    # Prevent admin from deleting themselves.
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.")
        return redirect(url_for("admin"))
    conn = sqlite3.connect("time_manager.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    # Optionally, you can also delete associated time_logs and diary entries.
    c.execute("DELETE FROM time_logs WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM diary WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully!")
    return redirect(url_for("admin"))

# ---------------------------
# Temporary Route to Reset the Database (Remove in Production)
# ---------------------------
@app.route("/reset_db")
def reset_db():
    db_path = "time_manager.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        init_db()
        flash("Database has been reset!")
    else:
        flash("Database file not found!")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
