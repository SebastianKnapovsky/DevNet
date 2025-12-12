# Mini DevOps Monitor (Flask + Docker)

Mini DevOps Monitor is a lightweight web application that **simulates CI/CD pipeline executions** (similar to GitHub Actions or GitLab CI),
stores results in JSON files, generates logs for each run, and presents basic DevOps metrics on a dashboard.

---

## 🎯 What does the application do?

1. Allows running simulated CI/CD pipelines:

   - `app-ci`
   - `api-ci`

2. Each pipeline executes a sequence of steps (e.g. `checkout`, `unit-tests`, `security-scan`, `deploy`).

   - steps have random execution time
   - steps have a configurable failure probability
   - run status changes from `running` → `success` or `failed`

3. For each pipeline run:
   - current state is saved to `builds.json` (used by the UI)
   - finished runs are appended to `history.json` (used for metrics)
   - logs are written to `logs/<run_id>.log`

---

## 🗂️ Data structure (files)

- **`devops_monitor.py`** – main Flask backend  
  Implements the API endpoints, pipeline simulation logic, file storage, and metrics calculations.

- **`templates/index.html`** – frontend dashboard page  
  Single-page UI rendered by Flask (`GET /`) that calls the API endpoints (builds, stats, logs, history download) and displays results.

- **`builds.json`** – current snapshot of recent pipeline runs  
  Used by the dashboard table. Updated while a pipeline is running.

- **`history.json`** – full history of finished runs (append-only)  
  Used to calculate DevOps metrics.

- **`logs/<run_id>.log`** – log file for a single pipeline run  
  Displayed in the UI when a run is selected.

- **`requirements.txt`** – Python dependencies list  
  Used for local install and Docker image build.

- **`Dockerfile`** – container build definition  
  Builds and runs the Flask application inside a Docker container (exposes port `5000`).

---

## 🖥️ Dashboard (UI)

The dashboard displays:

- **Deploys today** – number of completed runs today
- **Success rate (7d)** – success percentage from the last 7 days
- **Change Failure Rate (7d)** – failure percentage from the last 7 days
- **Avg duration** – average run duration (seconds)

The table shows pipeline runs with status, current step, duration, and timestamps.

- click a **row** → view logs
- click **Steps** → expand full pipeline steps

<img width="1388" height="827" alt="image" src="https://github.com/user-attachments/assets/d67b3e16-62a6-4834-9b2c-92c6879966d4" />

---

## ✅ Available actions (UI)

- **Run pipeline: app-ci** – start application pipeline
- **Run pipeline: api-ci** – start API pipeline
- **Reset** – clear builds, history, and logs
- **Download history** – download `history.json` file

---

## 🔌 API Endpoints

### UI

- **GET /**  
  Returns the main dashboard HTML page.

### Builds / Runs

- **GET /api/builds**  
  Returns the current snapshot of pipeline runs.

- **POST /api/run**  
  Starts a new pipeline execution.

### Logs

- **GET /api/logs/<run_id>**  
  Returns logs for a specific pipeline run.

### Metrics

- **GET /api/stats**  
  Returns aggregated DevOps metrics (deploys, success rate, CFR, average duration, MTTR).

### History

- **GET /api/history**  
  Returns the full history of finished pipeline runs.

- **GET /api/history/download**  
  Downloads the pipeline history as a JSON file.

### Reset

- **POST /api/reset**  
  Clears all stored data (builds, history, logs).

---

## ▶️ Run locally (without Docker)

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Start the application**

   ```bash
   python devops_monitor.py
   ```

3. **Open in browser**

   http://localhost:500

## 🐳 Running with Docker

1. **Build the image**

   ```bash
   docker build -t devops-monitor .
   ```

2. **Run the container**

   ```bash
   docker run -d -p 5000:5000 --name devops-monitor devops-monitor
   ```

3. **Open in browser**

   http://localhost:500
