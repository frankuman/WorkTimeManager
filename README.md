# Time Manager with Diary and Flex Time Calculation

This repository contains a Flask-based web application designed to help you manage your work hours with built-in diary functionality. The app tracks check‑in/check‑out times, calculates daily and weekly flex time (based on an 8‑hour workday), and lets you log diary entries—including an “active” diary mode for ongoing activities. In addition, it supports user authentication and an admin dashboard for managing users.

## Features

- **Time Tracking:**
  - Check in/out for work sessions.
  - Add past entries and edit existing ones.
  - Automatic calculation of flex time: each day is compared against an 8‑hour (480‑minute) baseline, and the weekly flex is the sum of daily differences.

- **Diary Functionality:**
  - Log diary entries for each work session.
  - **Active Diary Mode:** Activate an activity (e.g. “Coding”) which stays active until you deactivate it or check out.
  - Diary entries are grouped by day, with a collapsible view to show details for each day.
  - Generate reports that break down diary entries and work hours by week and by month.

- **User Authentication:**
  - Register, log in, and log out.
  - Each user’s data (time logs and diary entries) is isolated.
  - The logged‑in user’s name is displayed at the top of the dashboard.

- **Admin Dashboard:**
  - An admin account is automatically created if none exists (username: `admin`, password: `Inova20!0`).
  - Admin users are automatically redirected to the admin dashboard upon login.
  - Admins can view all registered users, reset user passwords, and delete users.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/time-manager.git
   cd time-manager
   ```

2. **Set Up a Virtual Environment:**

   ```bash
   python -m venv venv
   # On Linux/Mac:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   _Note: The `requirements.txt` file should list dependencies such as Flask and Werkzeug._

4. **Initialize/Reset the Database (if needed):**

   If you’re running the app for the first time or need to update the schema, delete the existing `time_manager.db` file or use the `/reset_db` route (visit `http://127.0.0.1:5000/reset_db` after starting the app).

## Usage

1. **Start the Application:**

   ```bash
   python app.py
   ```

2. **Access the App:**

   Open your browser and navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000).

3. **User Registration & Login:**
   - New users can register via the registration page.
   - For admin access, log in with:
     - **Username:** `admin`
     - **Password:** `Inova20!0`
   - Admin users are automatically redirected to the admin dashboard.

4. **Managing Your Time:**
   - Use the check‑in/out button to start or end a work session.
   - Add past entries manually if needed.
   - Your work sessions are compared against an 8‑hour baseline to calculate daily and weekly flex time.

5. **Diary Functionality:**
   - On the main dashboard, an active diary section lets you “Activate” an activity (e.g., “Coding”). When active, your activity is displayed along with its start time.
   - Press the "Deactivate" button to finish the activity.
   - Visit the `/diary` route to see diary entries grouped by day.
   - The `/diary_report` route provides a weekly and monthly breakdown of your diary entries and work hours.

6. **Admin Dashboard:**
   - The `/admin` route displays a list of all users.
   - Admins can reset any user’s password or delete a user account (except their own).

## Configuration

- **Secret Key:**
  - Update `app.secret_key` in `app.py` with a secure key before deploying to production.

- **Database:**
  - The application uses SQLite. The database file is named `time_manager.db`.

## Future Improvements

- Enhance the diary UI with JavaScript for smooth collapsible/expandable day views.
- Add more detailed reporting and analytics.
- Improve error handling and validation.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

