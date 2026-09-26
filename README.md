# 🎓 ODOCUST Academic Monitoring & Notification Agent

An intelligent, autonomous personal assistant that continuously monitors your **CUST Student Portal (ODOCUST / Tasjeel)** (`https://odoo.cust.edu.pk`), tracks all your courses, detects new assignments, projects, quizzes, and announcements, calculates approaching deadlines, tracks submission status, and delivers **smart WhatsApp alerts and reminders directly to your phone**.

---

## 🚀 Key Features

* **Continuous Automated Monitoring**: Checks the portal in the background every X minutes (default: 15 min, fully configurable) with near-zero memory footprint (< 30 MB).
* **Multi-Course Auto-Discovery**: Automatically extracts and maps all currently enrolled subjects from your dashboard (e.g. Design Project, Database Systems, Software Engineering).
* **Smart Deduplication**: Persistent SQLite database tracks every seen activity, hash, and status. **Zero duplicate spam.**
* **Intelligent Deadline Reminders**: Configurable countdown reminders (e.g. 72h, 48h, 24h, 12h, 6h, 3h, 1h). **Automatically ceases reminders once a task is submitted.**
* **Submission Status Verification**: Distinguishes between `Not Submitted`, `Submitted`, `Late Submitted`, and `Graded`. Alerts you immediately when a submission is successfully recorded or if an unsubmitted deadline approaches.
* **Smart Priority Engine**:
  * 🔴 **CRITICAL**: Deadlines < 24h, submission failure alerts, deadline moved earlier, urgent announcements.
  * 🟠 **HIGH**: Deadlines within 2–3 days, new projects (FYP, Capstone), new assignments.
  * 🟡 **NORMAL**: New assignments with plenty of time, general announcements.
  * 🟢 **LOW**: Informational lecture notes, course materials, slides.
* **Daily Academic Morning Briefing**: Automated morning summary on WhatsApp summarizing new items, upcoming deadlines, pending submissions, and completed tasks.
* **Interactive Local Dashboard**: Modern web UI running on `http://127.0.0.1:8080` with KPI cards, deadline countdown timeline, course grid, activity table, WhatsApp dispatch logs, and live settings management.
* **Multiple WhatsApp Gateways**: Built-in support for:
  1. **CallMeBot** (100% Free for personal WhatsApp, setup in 30 seconds)
  2. **Twilio WhatsApp API** (Enterprise-grade sandbox & official API)
  3. **Green-API** (Cloud gateway for personal/business accounts)
  4. **Console / Dashboard Log** (Local testing & zero-API verification)

---

## 🛠️ Technical Architecture

```text
       ODOCUST Student Portal (Odoo 15 @ odoo.cust.edu.pk)
                                │
                 [Authenticated Session Handler]
                 (CSRF extraction, auto re-login,
                  90-day cookie cache persistence)
                                │
                                ▼
                    [Academic Monitor Agent]
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[Dashboard Course Discovery]               [Course Scraper & Parser]
  - Discovers all enrolled subjects          - /student/course/info (News)
  - Detects course codes & hashes            - /student/course/submission (Tasks)
                                             - /student/course/assessment (Quizzes)
                                                        │
                                                        ▼
                                            [State & Diff Analyzer]
                                            (Compares against SQLite DB)
                                                        │
                                                        ▼
                                             [Academic Activity DB]
                                             (WAL Mode SQLite Persistence)
                                                        │
                      ┌─────────────────────────────────┴────────────────────────┐
                      ▼                                                          ▼
          [Deadline & Priority Engine]                               [FastAPI Local Dashboard]
          - Evaluates remaining hours                                 - Overview KPIs & stats
          - Matches 72h/48h/24h/12h checkpoints                       - Interactive timeline
          - Halts alerts on submission                                - Course cards & task table
                      │                                               - Live Settings Manager
                      ▼                                                          │
          [WhatsApp Dispatcher] ─────────────────────────────────────────────────┘
          (CallMeBot / Twilio / Green-API)
                      │
                      ▼
               Student's Phone
```

---

## 📦 Setup & Installation

### 1. Prerequisites
- Python 3.10+ (Python 3.14+ supported)
- Windows / macOS / Linux

### 2. Configure Environment
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Open `.env` and fill in your details:
```ini
# Portal Credentials
ODOCUST_BASE_URL=https://odoo.cust.edu.pk
ODOCUST_USERNAME=BSEXXXXXX
ODOCUST_PASSWORD=YourPortalPassword

# Optional: If you prefer browser cookie instead of password:
ODOCUST_SESSION_ID=

# Monitoring Frequency & Checkpoints
CHECK_INTERVAL_MINUTES=15
REMINDER_HOURS=72,48,24,12,6,3,1

# WhatsApp Configuration (Pick one provider)
WHATSAPP_PROVIDER=callmebot
WHATSAPP_TO_NUMBER=+923001234567

# If using CallMeBot (Easiest free option for personal numbers):
CALLMEBOT_PHONE=+923001234567
CALLMEBOT_API_KEY=your_callmebot_api_key
```

### 3. Quick Free WhatsApp Setup (CallMeBot)
1. Add the phone number **`+34 941 83 04 22`** to your phone contacts (name it "CallMeBot").
2. Send this exact message to it on WhatsApp:
   ```text
   I allow callmebot to send me messages
   ```
3. CallMeBot will reply within seconds with your unique **`apikey`** (e.g. `1234567`).
4. Paste that API key into your `.env` file under `CALLMEBOT_API_KEY`.

---

## 🏃 Running the Agent

### Windows (1-Click)
Double-click `start_agent.bat` or run:
```powershell
.\start_agent.bat
```

### Manual Command Line
```powershell
.\.venv\Scripts\python.exe main.py
```

Once running:
- Open your browser at **`http://127.0.0.1:8080`** to access the live dashboard!
- The background worker will run immediately, crawl your enrolled subjects, detect any new activities, and schedule all deadline countdowns.

---

## 🧪 Running the Test Suite

A complete verification test suite is included to validate the database, parser, countdown thresholds, priority classification, and message formatting:
```powershell
.\.venv\Scripts\python.exe test_suite.py
```
Expected output:
```text
Ran 5 tests in 0.35s
OK
```
