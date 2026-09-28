from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
import os, uuid, json, math, sqlite3
from datetime import datetime, timedelta

from services.land_service import analyze_image
from services.building_service import (
    calculate_materials, calculate_cost, calculate_labour,
    calculate_timeline, generate_floor_plan, recommend_building
)
from services.report_service import generate_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
DB_PATH = os.path.join(BASE_DIR, "landlensai.db")

for d in (UPLOAD_DIR, PROCESSED_DIR, REPORT_DIR):
    os.makedirs(d, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "landlensai-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED = {"png", "jpg", "jpeg", "webp"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS land_analysis(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        image_path TEXT,
        processed_path TEXT,
        data_json TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS buildings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        data_json TEXT,
        created_at TEXT NOT NULL
    );
    """)
    con.commit(); con.close()

init_db()

def allowed(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    image = request.files.get("image")
    project_name = request.form.get("project_name", "My Land Project").strip() or "My Land Project"
    if not image or not image.filename:
        flash("Please select a land image.")
        return redirect(url_for("home"))
    if not allowed(image.filename):
        flash("Use PNG, JPG, JPEG or WEBP.")
        return redirect(url_for("home"))

    ext = image.filename.rsplit(".",1)[1].lower()
    uid = uuid.uuid4().hex
    filename = f"{uid}.{ext}"
    path = os.path.join(UPLOAD_DIR, secure_filename(filename))
    image.save(path)

    try:
        result = analyze_image(path, PROCESSED_DIR, uid)
    except Exception as e:
        flash(f"Image processing failed: {e}")
        return redirect(url_for("home"))

    con = db()
    cur = con.execute("INSERT INTO projects(name,created_at) VALUES(?,?)",
                      (project_name, datetime.now().isoformat(timespec="seconds")))
    project_id = cur.lastrowid
    con.execute("""INSERT INTO land_analysis(project_id,image_path,processed_path,data_json,created_at)
                   VALUES(?,?,?,?,?)""",
                (project_id, f"uploads/{filename}", f"processed/{uid}_edges.jpg",
                 json.dumps(result), datetime.now().isoformat(timespec="seconds")))
    con.commit(); con.close()
    return redirect(url_for("land_result", project_id=project_id))

@app.route("/project/<int:project_id>")
def land_result(project_id):
    con = db()
    p = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    land = con.execute("SELECT * FROM land_analysis WHERE project_id=? ORDER BY id DESC LIMIT 1",
                       (project_id,)).fetchone()
    b = con.execute("SELECT * FROM buildings WHERE project_id=? ORDER BY id DESC LIMIT 1",
                    (project_id,)).fetchone()
    con.close()
    if not p or not land:
        flash("Project not found.")
        return redirect(url_for("home"))
    data = json.loads(land["data_json"])
    building = json.loads(b["data_json"]) if b else None
    return render_template("dashboard.html", project=p, land=data, land_row=land, building=building)

@app.route("/building/<int:project_id>", methods=["POST"])
def building(project_id):
    con = db()
    land = con.execute("SELECT * FROM land_analysis WHERE project_id=? ORDER BY id DESC LIMIT 1",
                       (project_id,)).fetchone()
    con.close()
    if not land:
        flash("Analyze land first.")
        return redirect(url_for("home"))

    def f(name, default=0):
        try: return float(request.form.get(name, default))
        except: return float(default)
    def i(name, default=0):
        try: return int(request.form.get(name, default))
        except: return int(default)

    building_type = request.form.get("building_type","Independent House")
    floors = max(1, i("floors",1))
    bedrooms = max(1, i("bedrooms",2))
    bathrooms = max(1, i("bathrooms",2))
    kitchens = max(1, i("kitchens",1))
    parking = request.form.get("parking","Yes")
    quality = request.form.get("quality","Standard")
    requested_area = f("built_area", 0)

    land_data = json.loads(land["data_json"])
    available = float(land_data.get("buildable_area_m2", 0))
    if requested_area <= 0:
        requested_area = round(available * 0.65, 2) if available > 0 else 120.0
    total_area = max(40.0, min(requested_area, max(40.0, available * floors if available else requested_area)))

    config = {
        "building_type": building_type, "floors": floors, "bedrooms": bedrooms,
        "bathrooms": bathrooms, "kitchens": kitchens, "parking": parking,
        "quality": quality, "built_area_m2": round(total_area,2)
    }
    materials = calculate_materials(total_area, floors, quality)
    cost = calculate_cost(materials, total_area, floors, quality)
    labour = calculate_labour(total_area, floors)
    timeline = calculate_timeline(total_area, floors)
    plan = generate_floor_plan(total_area, bedrooms, bathrooms, kitchens, parking)
    recommendation = recommend_building(land_data, config, cost)

    result = {"config":config, "materials":materials, "cost":cost, "labour":labour,
              "timeline":timeline, "floor_plan":plan, "recommendation":recommendation}

    con = db()
    con.execute("INSERT INTO buildings(project_id,data_json,created_at) VALUES(?,?,?)",
                (project_id, json.dumps(result), datetime.now().isoformat(timespec="seconds")))
    con.commit(); con.close()
    return redirect(url_for("land_result", project_id=project_id))

@app.route("/report/<int:project_id>")
def report(project_id):
    con = db()
    p = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    land = con.execute("SELECT * FROM land_analysis WHERE project_id=? ORDER BY id DESC LIMIT 1",(project_id,)).fetchone()
    b = con.execute("SELECT * FROM buildings WHERE project_id=? ORDER BY id DESC LIMIT 1",(project_id,)).fetchone()
    con.close()
    if not p or not land or not b:
        flash("Complete land analysis and building configuration before generating the report.")
        return redirect(url_for("land_result", project_id=project_id))
    data = json.loads(land["data_json"]); building_data = json.loads(b["data_json"])
    out = os.path.join(REPORT_DIR, f"LandLensAI_Report_{project_id}.pdf")
    generate_report(out, dict(p), data, building_data)
    return send_file(out, as_attachment=True, download_name=os.path.basename(out))

@app.route("/api/projects")
def api_projects():
    con=db()
    rows=con.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    con.close()
    return jsonify([dict(x) for x in rows])

@app.route("/api/project/<int:project_id>")
def api_project(project_id):
    con=db()
    p=con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    land=con.execute("SELECT * FROM land_analysis WHERE project_id=? ORDER BY id DESC LIMIT 1",(project_id,)).fetchone()
    b=con.execute("SELECT * FROM buildings WHERE project_id=? ORDER BY id DESC LIMIT 1",(project_id,)).fetchone()
    con.close()
    if not p: return jsonify({"error":"not found"}),404
    return jsonify({"project":dict(p), "land":json.loads(land["data_json"]) if land else None,
                    "building":json.loads(b["data_json"]) if b else None})

@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_file(os.path.join(UPLOAD_DIR, filename))

@app.route("/processed/<path:filename>")
def processed(filename):
    return send_file(os.path.join(PROCESSED_DIR, filename))

@app.errorhandler(413)
def too_large(e):
    flash("Image is too large. Maximum size is 10 MB.")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
