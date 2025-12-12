import glob
from flask import Flask, jsonify, render_template, request, Response
import json, os, threading, time, random, uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

app = Flask(__name__)

DATA_CURRENT = "builds.json"      
DATA_HISTORY = "history.json"     
LOGS_DIR = "logs"                
os.makedirs(LOGS_DIR, exist_ok=True)

PIPELINE = {
    "app-ci": [
        "checkout",
        "install-deps",
        "lint",
        "unit-tests",
        "build-artifact",
        "deploy-staging"
    ],
    "api-ci": [
        "checkout",
        "install-deps",
        "unit-tests",
        "integration-tests",
        "security-scan",
        "docker-build",
        "deploy-prod"
    ]
}

STEP_TIME = {
    "checkout": (0.4, 0.9),
    "install-deps": (0.8, 1.6),
    "lint": (0.6, 1.4),
    "unit-tests": (1.0, 2.5),
    "integration-tests": (1.3, 3.0),
    "security-scan": (1.0, 2.8),
    "build-artifact": (0.8, 1.8),
    "docker-build": (1.2, 3.2),
    "deploy-staging": (0.9, 2.0),
    "deploy-prod": (1.2, 2.6),
}

STEP_FAIL_PROB = {
    "checkout": 0.01,
    "install-deps": 0.04,
    "lint": 0.10,
    "unit-tests": 0.12,
    "integration-tests": 0.18,
    "security-scan": 0.22,
    "build-artifact": 0.05,
    "docker-build": 0.08,
    "deploy-staging": 0.10,
    "deploy-prod": 0.16,
}


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default


def _save_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _append_history(entry: Dict[str, Any]):
    hist = _load_json(DATA_HISTORY, [])
    hist.append(entry)
    _save_json(DATA_HISTORY, hist)


def _write_log(run_id: str, line: str):
    p = os.path.join(LOGS_DIR, f"{run_id}.log")
    with open(p, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def _simulate_step_output(step: str) -> str:
    if step == "lint":
        return "Lint: flake8 passed (0 errors)"
    if step == "unit-tests":
        return f"Unit tests: {random.randint(80, 220)} passed"
    if step == "integration-tests":
        return f"Integration tests: {random.randint(25, 90)} passed"
    if step == "security-scan":
        vulns = random.choice([0, 0, 1, 2, 3])
        return f"Security scan: found {vulns} issues (sev: low/med/high mixed)"
    if step == "docker-build":
        return "Docker build: image tagged 'app:latest'"
    if step.startswith("deploy"):
        return f"Deploy: rollout completed, healthcheck OK"
    if step == "install-deps":
        return "Dependencies installed successfully"
    if step == "checkout":
        return "Checked out repository"
    if step == "build-artifact":
        return "Build artifact created: dist/app.zip"
    return "Step completed"


def _simulate_pipeline(run: Dict[str, Any]):
    run_id = run["id"]
    steps = run["steps"]
    start = time.time()

    _write_log(run_id, f"[{_utcnow_iso()}] Run {run_id} started (job={run['job']})")

    for step in steps:
        run["current_step"] = step
        _save_current_snapshot(run)  

        _write_log(run_id, f"[{_utcnow_iso()}] Step '{step}' started")
        tmin, tmax = STEP_TIME.get(step, (0.8, 1.8))
        time.sleep(random.uniform(tmin, tmax))

        _write_log(run_id, f"[{_utcnow_iso()}] { _simulate_step_output(step) }")

        fail_prob = STEP_FAIL_PROB.get(step, 0.10)
        if random.random() < fail_prob:
            run["status"] = "failed"
            run["finished_at"] = _utcnow_iso()
            run["duration_s"] = int(time.time() - start)
            _write_log(run_id, f"[{_utcnow_iso()}] Step '{step}' FAILED")
            _write_log(run_id, f"[{_utcnow_iso()}] Run {run_id} finished with status=failed")
            run["current_step"] = None
            _save_current_snapshot(run)
            _append_history(run)
            return
        else:
            _write_log(run_id, f"[{_utcnow_iso()}] Step '{step}' OK")

    run["status"] = "success"
    run["finished_at"] = _utcnow_iso()
    run["duration_s"] = int(time.time() - start)
    run["current_step"] = None
    _write_log(run_id, f"[{_utcnow_iso()}] Run {run_id} finished with status=success")

    _save_current_snapshot(run)
    _append_history(run)


def _save_current_snapshot(run: Dict[str, Any]):
    curr = _load_json(DATA_CURRENT, [])
    curr = [x for x in curr if x.get("id") != run["id"]]
    curr.insert(0, run)
    _save_json(DATA_CURRENT, curr[:100])


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/builds")
def api_builds():
    return jsonify(_load_json(DATA_CURRENT, []))


@app.get("/api/logs/<run_id>")
def api_logs(run_id):
    p = os.path.join(LOGS_DIR, f"{run_id}.log")
    if not os.path.exists(p):
        return jsonify({"log": ""})
    with open(p, encoding="utf-8") as f:
        return jsonify({"log": f.read()})


@app.post("/api/run")
def api_run():
    data = request.get_json(silent=True) or {}
    job = data.get("job") or "app-ci"
    steps = PIPELINE.get(job, ["checkout", "unit-tests", "deploy-staging"])

    run = {
        "id": uuid.uuid4().hex[:8],
        "job": job,
        "status": "running",
        "steps": steps,
        "current_step": steps[0] if steps else None,
        "started_at": _utcnow_iso(),
        "finished_at": None,
        "duration_s": None
    }

    _save_current_snapshot(run)

    threading.Thread(target=_simulate_pipeline, args=(run,), daemon=True).start()
    return jsonify({"message": "started", "run_id": run["id"]})


def _calc_stats() -> Dict[str, Any]:
    hist: List[Dict[str, Any]] = _load_json(DATA_HISTORY, [])
    if not hist:
        return {"deploys_today": 0, "success_rate": 0, "cfr": 0, "avg_duration": 0, "mttr_minutes": 0}

    now = datetime.utcnow()
    finished = [h for h in hist if h.get("finished_at")]

    today = [
        h for h in finished
        if datetime.fromisoformat(h["finished_at"].rstrip("Z")).date() == now.date()
    ]
    last7 = [
        h for h in finished
        if now - datetime.fromisoformat(h["finished_at"].rstrip("Z")) <= timedelta(days=7)
    ]

    total = len(last7)
    failures = sum(1 for h in last7 if h["status"] == "failed")
    successes = sum(1 for h in last7 if h["status"] == "success")

    avg_dur = 0
    ds = [h.get("duration_s") for h in last7 if h.get("duration_s")]
    if ds:
        avg_dur = int(sum(ds) / len(ds))

    mttrs = []
    for h in last7:
        if h["status"] != "failed":
            continue
        t_fail = datetime.fromisoformat(h["finished_at"].rstrip("Z"))
        later = [
            x for x in last7
            if x["job"] == h["job"]
            and x.get("finished_at")
            and datetime.fromisoformat(x["finished_at"].rstrip("Z")) > t_fail
            and x["status"] == "success"
        ]
        if later:
            t_succ = min(datetime.fromisoformat(x["finished_at"].rstrip("Z")) for x in later)
            mttrs.append((t_succ - t_fail).total_seconds() / 60)
    mttr = int(sum(mttrs) / len(mttrs)) if mttrs else 0

    return {
        "deploys_today": len(today),
        "success_rate": round((successes / total) * 100, 1) if total else 0.0,
        "cfr": round((failures / total) * 100, 1) if total else 0.0,
        "avg_duration": avg_dur,
        "mttr_minutes": mttr
    }


@app.get("/api/stats")
def api_stats():
    return jsonify(_calc_stats())

@app.post("/api/reset")
def api_reset():
    _save_json(DATA_CURRENT, [])
    _save_json(DATA_HISTORY, [])

    if os.path.exists(LOGS_DIR):
        for p in glob.glob(os.path.join(LOGS_DIR, "*.log")):
            try:
                os.remove(p)
            except Exception:
                pass

    return jsonify({"message": "reset done"})

@app.get("/api/history")
def api_history():
    hist = _load_json(DATA_HISTORY, [])
    return jsonify(hist)


@app.get("/api/history/download")
def api_history_download():
    hist = _load_json(DATA_HISTORY, [])
    payload = json.dumps(hist, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=history.json"}
    )


if __name__ == "__main__":
    if not os.path.exists(DATA_CURRENT):
        _save_json(DATA_CURRENT, [])
    app.run(host="0.0.0.0", port=5000, debug=True)
