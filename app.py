from flask import Flask, request, jsonify, render_template, redirect ,send_from_directory
from flask_cors import CORS
import os
import bcrypt
from werkzeug.utils import secure_filename
import geopandas as gpd
import traceback
import os
import subprocess
import sys
import pandas as pd
import random
import smtplib
from email.mime.text import MIMEText
from flask import session
from werkzeug.utils import secure_filename
import shutil
from flask import Flask, jsonify, send_from_directory, request
import geopandas as gpd
import traceback
import os
import subprocess
from flask_cors import CORS
import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from flask import session, request, redirect, render_template
from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from scripts.admin_raster_clip import (
    admin_clip_precipitation_raster,
    admin_clip_temperature_raster,
    collaborator_clip_precipitation_raster,
    collaborator_clip_temperature_raster

)
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, template_folder="template")
CORS(app)
district_cache = None
mean_cache = {}
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_UPLOAD = "data"
os.makedirs(BASE_UPLOAD, exist_ok=True)

@app.route("/")
def home():
    return send_from_directory(os.path.join(BASE_DIR, "template"), "Home.html")

######   viewer routes ####################

@app.route("/viewer/display")
def viewer_display():
    return send_from_directory(os.path.join(BASE_DIR, "template","viewer"), "display.html")


@app.route("/viewer/output")
def viewer_output():
    return send_from_directory(os.path.join(BASE_DIR, "template", "viewer"), "output.html")

app.secret_key = os.getenv("SECRET_KEY")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_otp(email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Viewer Login OTP"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


@app.route("/viewer/login", methods=["GET", "POST"])
def viewer_login():

    # STEP 1 → Send OTP
    if request.method == "POST" and "email" in request.form:
        email = request.form.get("email")

        otp = str(random.randint(100000, 999999))
        session["otp"] = otp
        session["email"] = email
        session["otp_sent"] = True

        send_otp(email, otp)

        return render_template("viewer/login.html", otp_sent=True)

    # STEP 2 → Verify OTP
    if request.method == "POST" and "otp" in request.form:
        user_otp = request.form.get("otp")

        if user_otp == session.get("otp"):
            return redirect("/viewer/display")
        else:
            return render_template(
                "viewer/login.html",
                otp_sent=True,
                error="Invalid OTP"
            )

    return render_template("viewer/login.html")


########## admin routes

# 🔐 Hardcoded admin credentials
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


@app.route("/admin/login", methods=['GET', 'POST'])
def admin_login():
   
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # check credentials
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
             session["admin-logged-in"]=True
             return redirect("/admin/display")
        else:
            return render_template("admin/login.html", error="Invalid credentials")

    return render_template("admin/login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin-logged-in', None)
    return redirect("/")

@app.route("/admin/display")
def admin_display():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template","admin"), "display.html")

@app.route("/admin/output")
def admin_output():
    if "admin-logged-in" not in session:
        return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template", "admin"), "output.html")


@app.route("/run", methods=["GET", "POST"])
def run_admin_gnn_pipeline():
    if "admin-logged-in" not in session:
        if request.method == "POST":
            return jsonify({"error": "Unauthorized"}), 401
        return render_template("admin/login.html", error="You are not Authorised . Login First ")

    scripts_dir = os.path.join(BASE_DIR, "data", "admin", "gnn")
    ordered_scripts = [
        "app.py",
        "app_testing.py",
        "gnn_training.py",
        "gnn_testing.py",
        "generate_rasters.py",
    ]

    candidate_pythons = [
        os.path.join(scripts_dir, "venv", "bin", "python"),
        os.path.join(scripts_dir, "venv", "Scripts", "python.exe"),
        os.path.join(BASE_DIR, "data", "admin", "gnn", "venv", "bin", "python"),
        os.path.join(BASE_DIR, "data", "admin", "gnn", "venv", "Scripts", "python.exe"),
        os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe"),
        os.path.join(BASE_DIR, ".venv", "bin", "python"),
        sys.executable,
    ]

    python_cmd = None
    for candidate in candidate_pythons:
        if not os.path.exists(candidate):
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "import torch"],
                capture_output=True,
                text=True,
            )
        except OSError:
            # Skip incompatible executables (e.g., Windows python.exe from Linux/WSL).
            continue
        if probe.returncode == 0:
            python_cmd = candidate
            break

    if python_cmd is None:
        return jsonify({
            "error": "No Python environment with torch found for admin pipeline",
            "details": "Install torch in data/admin/gnn/venv or use a compatible environment with torch."
        }), 500

    try:
        for script_name in ordered_scripts:
            script_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(script_path):
                return jsonify({"error": f"Missing script: {script_path}"}), 404

            completed = subprocess.run(
                [python_cmd, script_path],
                check=True,
                cwd=scripts_dir,
                capture_output=True,
                text=True,
            )

            if completed.stdout:
                print(completed.stdout)

        output_url = "/admin/output"
        if request.method == "POST":
            return jsonify({"message": "Pipeline completed", "redirect": output_url}), 200
        return redirect(output_url)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        details = stderr if stderr else stdout
        return jsonify({
            "error": f"Pipeline failed at {e.cmd}",
            "details": details or str(e)
        }), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/admin/modelling')
def admin_home():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template","admin"), "modelling.html")


@app.route("/api/admin-gnn-wqi-rasters", methods=["GET"])
def admin_gnn_wqi_rasters():
    if "admin-logged-in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    raster_dir = os.path.join(BASE_DIR, "data", "admin", "gnn", "wqi_rasters")
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if not os.path.exists(raster_dir):
        return jsonify({"years": [], "monthsByYear": {}, "rasters": []})

    import re
    parsed = []
    for fname in os.listdir(raster_dir):
        match = re.match(r"^wqi_(\d{4})_(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.tif$", fname)
        if not match:
            continue

        year = int(match.group(1))
        month = match.group(2)
        parsed.append({
            "year": year,
            "month": month,
            "monthIndex": month_order.index(month),
            "file": fname,
            "url": f"/data/admin/gnn/wqi_rasters/{fname}"
        })

    parsed.sort(key=lambda x: (x["year"], x["monthIndex"]))

    years = sorted({item["year"] for item in parsed})
    months_by_year = {}
    for y in years:
        months = [item["month"] for item in parsed if item["year"] == y]
        months_by_year[str(y)] = months

    return jsonify({
        "years": years,
        "monthsByYear": months_by_year,
        "rasters": [{
            "year": item["year"],
            "month": item["month"],
            "file": item["file"],
            "url": item["url"]
        } for item in parsed]
    })


@app.route("/api/viewer-gnn-wqi-rasters", methods=["GET"])
def viewer_gnn_wqi_rasters():
    raster_dir = os.path.join(BASE_DIR, "data", "admin", "gnn", "wqi_rasters")
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if not os.path.exists(raster_dir):
        return jsonify({"years": [], "monthsByYear": {}, "rasters": []})

    import re
    parsed = []
    for fname in os.listdir(raster_dir):
        match = re.match(r"^wqi_(\d{4})_(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.tif$", fname)
        if not match:
            continue

        year = int(match.group(1))
        month = match.group(2)
        parsed.append({
            "year": year,
            "month": month,
            "monthIndex": month_order.index(month),
            "file": fname,
            "url": f"/data/admin/gnn/wqi_rasters/{fname}"
        })

    parsed.sort(key=lambda x: (x["year"], x["monthIndex"]))

    years = sorted({item["year"] for item in parsed})
    months_by_year = {}
    for y in years:
        months = [item["month"] for item in parsed if item["year"] == y]
        months_by_year[str(y)] = months

    return jsonify({
        "years": years,
        "monthsByYear": months_by_year,
        "rasters": [{
            "year": item["year"],
            "month": item["month"],
            "file": item["file"],
            "url": item["url"]
        } for item in parsed]
    })


@app.route("/api/collaborator-gnn-wqi-rasters", methods=["GET"])
def collaborator_gnn_wqi_rasters():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    collab_id=session['collab_id']
    raster_dir = os.path.join(BASE_DIR, "data", "collaborator",collab_id, "gnn", "wqi_rasters")
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if not os.path.exists(raster_dir):
        return jsonify({"years": [], "monthsByYear": {}, "rasters": []})

    import re
    parsed = []
    for fname in os.listdir(raster_dir):
        match = re.match(r"^wqi_(\d{4})_(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.tif$", fname)
        if not match:
            continue

        year = int(match.group(1))
        month = match.group(2)
        parsed.append({
            "year": year,
            "month": month,
            "monthIndex": month_order.index(month),
            "file": fname,
            "url": f"/data/collaborator/{collab_id}/gnn/wqi_rasters/{fname}"
        })

    parsed.sort(key=lambda x: (x["year"], x["monthIndex"]))

    years = sorted({item["year"] for item in parsed})
    months_by_year = {}
    for y in years:
        months = [item["month"] for item in parsed if item["year"] == y]
        months_by_year[str(y)] = months

    return jsonify({
        "years": years,
        "monthsByYear": months_by_year,
        "rasters": [{
            "year": item["year"],
            "month": item["month"],
            "file": item["file"],
            "url": item["url"]
        } for item in parsed]
    })

@app.route("/admin/upload/display")
def admin_upload_display():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template","admin"), "upload_display.html")

@app.route("/admin/upload/training")
def admin_upload_training():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template","admin"), "upload_training.html")

@app.route("/admin/upload/testing")
def admin_upload_testing():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    return send_from_directory(os.path.join(BASE_DIR, "template","admin"), "upload_testing.html")


def clear_directory_contents(folder_path):
    if not os.path.exists(folder_path):
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}: {e}")
            raise


@app.route("/admin/clear/display", methods=["POST"])
def admin_clear_display():
    if "admin-logged-in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "admin", "display")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Display directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/clear/training", methods=["POST"])
def admin_clear_training():
    if "admin-logged-in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "admin", "gnn", "training_input")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Training directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/clear/testing", methods=["POST"])
def admin_clear_testing():
    if "admin-logged-in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "admin", "gnn", "testing_input")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Testing directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/upload/stations", methods=["GET", "POST"])
def admin_upload_stations():
    if "admin-logged-in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "No file provided"}), 400
        if not file.filename.endswith(".csv"):
            return jsonify({"error": "Only CSV files are accepted"}), 400

        save_dir = os.path.join(BASE_DIR, "data", "admin", "gnn")
        os.makedirs(save_dir, exist_ok=True)
        file.save(os.path.join(save_dir, "upstream_to_downstream_stations.csv"))
        return jsonify({"message": "Station topology uploaded successfully"}), 200

    return jsonify({"error": "Method not allowed"}), 405

@app.route("/api/admin-upload-testing-data", methods=["POST"])
def admin_upload_testing_data():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    try:
        file = request.files.get("file")
        upload_type = (request.form.get("upload_type") or "csv").strip().lower()

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        type_config = {
            "csv": {
                "extension": ".csv",
                "folder": os.path.join(BASE_DIR, "data", "admin", "gnn", "testing_input")
            },
            "lulc": {
                "extension": ".tif",
                "folder": os.path.join(BASE_DIR, "data", "admin", "gnn", "testing_input", "lulc")
            },
            "pop": {
                "extension": ".tif",
                "folder": os.path.join(BASE_DIR, "data", "admin", "gnn", "testing_input", "pop")
            }
        }

        if upload_type not in type_config:
            return jsonify({"error": "Invalid upload type"}), 400

        expected_ext = type_config[upload_type]["extension"]
        if not file.filename.lower().endswith(expected_ext):
            return jsonify({"error": f"Only {expected_ext} files allowed for {upload_type}"}), 400

        upload_folder = type_config[upload_type]["folder"]
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)

        file.save(file_path)

        return jsonify({
            "message": f"Testing {upload_type} uploaded successfully",
            "file_path": file_path
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin-update-stations-training-data", methods=["POST"])
def update_all_stations_training():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    try:
        upload_type = (request.form.get("upload_type") or "").strip().lower()
        if upload_type in {"lulc", "pop"}:
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "No file uploaded"}), 400

            if not file.filename.lower().endswith(".tif"):
                return jsonify({"error": f"Only .tif files allowed for {upload_type}"}), 400

            raster_upload_folder = os.path.join(
                BASE_DIR,
                "data",
                "admin",
                "gnn",
                "training_input",
                upload_type,
            )
            os.makedirs(raster_upload_folder, exist_ok=True)

            filename = secure_filename(file.filename)
            file_path = os.path.join(raster_upload_folder, filename)
            file.save(file_path)

            return jsonify({
                "message": f"Training {upload_type} uploaded successfully",
                "file_path": file_path
            }), 200

        year = int(request.form.get("year"))
        month_input = request.form.get("month")
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        df = pd.read_csv(file)

        if "station" not in df.columns:
            return jsonify({"error": "Missing 'station' column"}), 400

        df.set_index("station", inplace=True)

        BASE = os.path.join(BASE_DIR, "data", "admin", "gnn", "training_input")

        month_map = {
            "1": "Jan", "2": "Feb", "3": "Mar",
            "4": "Apr", "5": "May", "6": "Jun",
            "7": "Jul", "8": "Aug", "9": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }
        month = month_map.get(str(month_input), month_input)

        updated = []


        # ---------- LOOP ----------
        for station in df.index:

            station_file = station if station.startswith("Station_") else station.split("_")[0]

            
            for j in df.columns:
                val = df.loc[station, j]

                if not pd.isna(val):
                    path = os.path.join(BASE, j, f"{station}.csv")
                    os.makedirs(os.path.dirname(path), exist_ok=True)

                    if os.path.exists(path):
                        station_df = pd.read_csv(path)
                    else:
                        station_df = pd.DataFrame(columns=["Year","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                    mask = station_df["Year"] == year if not station_df.empty else []

                    if len(mask) > 0 and any(mask):
                        station_df.loc[mask, month] = val
                    else:
                        new_row = {col: None for col in station_df.columns}
                        new_row["Year"] = year
                        new_row[month] = val
                        station_df = pd.concat([station_df, pd.DataFrame([new_row])], ignore_index=True)

                    station_df.to_csv(path, index=False)

           

           

            updated.append(station)


        return jsonify({"message": "Training updated", "stations": updated}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin-update-stations-display", methods=["POST"])
def update_all_stations_display():
    if "admin-logged-in" not in session:
         return render_template("admin/login.html", error="You are not Authorised . Login First ")
    try:
        upload_type = (request.form.get("upload_type") or "csv").strip().lower()
        if upload_type in {"lulc", "pop"}:
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "No file uploaded"}), 400

            if not file.filename.lower().endswith(".tif"):
                return jsonify({"error": f"Only .tif files allowed for {upload_type}"}), 400

            raster_upload_folder = os.path.join(
                BASE_DIR,
                "data",
                "admin",
                "display",
                "raster",
                upload_type,
            )
            os.makedirs(raster_upload_folder, exist_ok=True)

            filename = secure_filename(file.filename)
            file_path = os.path.join(raster_upload_folder, filename)
            file.save(file_path)

            return jsonify({
                "message": f"Display {upload_type} uploaded successfully",
                "file_path": file_path
            }), 200

        year = int(request.form.get("year"))
        month_input = request.form.get("month")
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        df = pd.read_csv(file)

        if "station" not in df.columns:
            return jsonify({"error": "Missing 'station' column"}), 400

        df.set_index("station", inplace=True)

        BASE = os.path.join(BASE_DIR, "data", "admin", "display")

        month_map = {
            "1": "Jan", "2": "Feb", "3": "Mar",
            "4": "Apr", "5": "May", "6": "Jun",
            "7": "Jul", "8": "Aug", "9": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }
        month = month_map.get(str(month_input), month_input)

        updated = []


        # ---------- LOOP ----------
        for station in df.index:

            station_file = station if station.startswith("Station_") else station.split("_")[0]

            # ---------- PRECIP ----------
            for j in df.columns:
                val = df.loc[station, j]

                if not pd.isna(val):
                    path = os.path.join(BASE, j, f"{station}.csv")
                    os.makedirs(os.path.dirname(path), exist_ok=True)

                    if os.path.exists(path):
                        station_df = pd.read_csv(path)
                    else:
                        station_df = pd.DataFrame(columns=["Year","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                    mask = station_df["Year"] == year if not station_df.empty else []

                    if len(mask) > 0 and any(mask):
                        station_df.loc[mask, month] = val
                    else:
                        new_row = {col: None for col in station_df.columns}
                        new_row["Year"] = year
                        new_row[month] = val
                        station_df = pd.concat([station_df, pd.DataFrame([new_row])], ignore_index=True)

                    station_df.to_csv(path, index=False)


            updated.append(station)

    

        return jsonify({"message": "Display updated", "stations": updated}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def serve_data(filename):
    return send_from_directory("data", filename)


@app.route("/api/admin-generate-precip-year")
def admin_generate_precip_year():
    try:
        year = request.args.get("year", type=int)

        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for year {year}...")

        script_path =os.path.join(BASE_DIR, "scripts", "admin_interpolation_precp.py")

       
        subprocess.run(
            ["python3", script_path, str(year)],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "admin",
            "display",
            "precip",
            "output_precip_rasters",
            f"precip_{year}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/admin/display/precip/output_precip_rasters/precip_{year}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin-generate-temp-year")
def admin_generate_temp_year():
    try:
        year = request.args.get("year", type=int)

        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for year {year}...")

        script_path =os.path.join(BASE_DIR, "scripts", "admin_interpolation_temp.py")

       
        subprocess.run(
            ["python3", script_path, str(year)],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "admin",
            "display",
            "temp",
            "output_temp_rasters",
            f"temp_{year}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/admin/display/temp/output_temp_rasters/temp_{year}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin-generate-streamflow-year")
def admin_generate_streamflow_year():
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=str)
        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for {year , month}...")

        script_path =os.path.join(BASE_DIR, "scripts", "admin_interpolation_stream_flow.py")

       
        subprocess.run(
            ["python3", script_path, str(year),month],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "admin",
            "display",
            "streamflow",
            "output_streamflow_rasters",
            f"streamflow_{year}_{month}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year , month}",
            "file": f"data/admin/display/streamflow/output_streamflow_rasters/streamflow_{year}_{month}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin-generate-waterlevel-year")
def admin_generate_waterlevel_year():
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=str)
        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for {year , month}...")

        script_path =os.path.join(BASE_DIR, "scripts", "admin_interpolation_water_level.py")

       
        subprocess.run(
            ["python3", script_path, str(year),month],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "admin",
            "display",
            "waterlevel",
            "output_waterlevel_rasters",
            f"waterlevel_{year}_{month}_30m.tif"
        )

        
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/admin/display/waterlevel/output_waterlevel_rasters/waterlevel_{year}_{month}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin-clip-precip")
def admin_clip_precip():
    try:
        admin_clip_precipitation_raster()
        return jsonify({"message": "Precipitation raster clipped successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin-clip-temperature")
def admin_clip_temperature():
    try:
        admin_clip_temperature_raster()
        return jsonify({"message": "Mean temperature raster clipped successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin-rivers-per-district")
def admin_rivers_per_district():
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        district_path = os.path.join(BASE_DIR, "data","admin","display", "geojson", "district_boundary.geojson")
        river_path = os.path.join(BASE_DIR, "data","admin","display", "geojson", "narmada_named_network.geojson")


        districts = gpd.read_file(district_path)
        rivers = gpd.read_file(river_path)

        if districts.crs is None:
            districts.set_crs("EPSG:4326", inplace=True)
        if rivers.crs is None:
            rivers.set_crs("EPSG:4326", inplace=True)

        if districts.crs != rivers.crs:
            rivers = rivers.to_crs(districts.crs)

        result = []

        for _, d in districts.iterrows():
            district_name = d.get("District", "Unknown")
            district_geom = d.geometry

            if district_geom is None or district_geom.is_empty:
                continue

            def safe_intersect(geom):
                try:
                    return geom is not None and not geom.is_empty and geom.intersects(district_geom)
                except:
                    return False

            intersecting = rivers[rivers.geometry.apply(safe_intersect)]

            river_names = []
            if "River_Name" in intersecting.columns:
                river_names = intersecting["River_Name"].dropna().unique().tolist()

            if river_names:
                result.append({
                    "district": district_name,
                    "river_count": len(river_names),
                    "river_names": river_names
                })

        result.sort(key=lambda x: x["district"])
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin-districts")
def admin_districts():
    global district_cache
    if district_cache is not None:
        return jsonify(district_cache)

    districts_gdf = gpd.read_file(os.path.join(BASE_DIR, "data","admin","display", "geojson", "district_boundary.geojson")).to_crs("EPSG:4326")
    narmada = gpd.read_file(os.path.join(BASE_DIR, "data","admin","display", "geojson", "narmada.geojson")).to_crs("EPSG:4326")
    narmada_geom = narmada.geometry.union_all()
    filtered = districts_gdf[districts_gdf.intersects(narmada_geom)]
    district_cache = sorted(filtered["District"].dropna().unique().tolist())
    return jsonify(district_cache)


@app.route("/api/admin-mean")
def admin_mean():
    district = request.args.get("district")
    if not district:
        return jsonify({"error": "No district provided"})

    if district in mean_cache:
        return jsonify({"output": mean_cache[district]})

    try:
        script_path = os.path.join(BASE_DIR, "scripts", "perdistrict.py")
        result = subprocess.run(
            [sys.executable, script_path],
            input=district,
            text=True,
            capture_output=True,
            cwd=BASE_DIR,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "Failed to compute district means").strip()
            return jsonify({"error": details})

        output = result.stdout
        mean_cache[district] = output
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/admin-get-years/<dataset>")
def admin_get_years(dataset):

    base_path = os.path.join(BASE_DIR, "data", "admin", "display")

    try:

        # ===============================
        # ✅ LULC & POP (RASTER)
        # ===============================
        if dataset in ["lulc", "pop"]:

            folder = os.path.join(base_path, "raster",dataset)

            if not os.path.exists(folder):
                return jsonify([])

            years = set()

            for file in os.listdir(folder):

                if not file.endswith(".tif"):
                    continue

                # 🔥 Extract year using regex (robust)
                import re
                match = re.search(r"(19|20)\d{2}", file)

                if match:
                    years.add(int(match.group()))

            return jsonify(sorted(years))


        # ======================================
        # ✅ CSV DATA (COLUMN-BASED YEARS)
        # ======================================
        else:

            folder_map = {
                "precip": "precip",
                "temp": "temp",
                "streamflow": "streamflow",
                "waterlevel": "waterlevel"
            }

            folder = os.path.join(base_path, folder_map.get(dataset, ""))

            if not os.path.exists(folder):
                return jsonify([])

            csv_files = [
                f for f in os.listdir(folder)
                if f.endswith(".csv") and not f.lower().startswith("sample")
            ]

            if not csv_files:
                return jsonify([])

            years = set()

            for csv_name in csv_files:
                csv_path = os.path.join(folder, csv_name)

                try:
                    header_cols = pd.read_csv(csv_path, nrows=0).columns.tolist()
                    if not header_cols:
                        continue

                    year_col = next(
                        (c for c in header_cols if str(c).strip().lower() == "year"),
                        header_cols[0]
                    )

                    df = pd.read_csv(csv_path, usecols=[year_col])
                    numeric_years = pd.to_numeric(df[year_col], errors="coerce").dropna().astype(int)

                    for y in numeric_years:
                        if 1800 < y < 3000:
                            years.add(int(y))
                except Exception:
                    continue

            return jsonify(sorted(list(years)))


    except Exception as e:
        print("Year detection error:", e)
        return jsonify([])


@app.route("/api/admin-raster-range-meta", methods=["GET"])
def admin_raster_range_meta():
    raster_dir = os.path.join(BASE_DIR, "data", "admin", "display", "raster")

    def pick_file(kind):
        if not os.path.exists(raster_dir):
            return None

        candidates = []
        for fname in os.listdir(raster_dir):
            lower = fname.lower()
            if not lower.endswith(".tif"):
                continue
            if "clipped" in lower:
                continue

            if kind == "precip":
                if "precip" not in lower and "precipiration" not in lower:
                    continue
            elif kind == "temp":
                if "temp" not in lower and "temperature" not in lower:
                    continue

            import re
            match = re.match(r"^((?:19|20)\d{2})_((?:19|20)\d{2})_(.+)\.tif$", fname)
            if not match:
                continue

            start_year = int(match.group(1))
            end_year = int(match.group(2))
            candidates.append((start_year, end_year, fname))

        if not candidates:
            return None

        # Prefer latest range if multiple files exist.
        start_year, end_year, selected = sorted(candidates, key=lambda x: (x[0], x[1]))[-1]
        return {
            "file": selected,
            "startYear": start_year,
            "endYear": end_year,
        }

    precip_meta = pick_file("precip")
    temp_meta = pick_file("temp")

    return jsonify({
        "precip": precip_meta,
        "temp": temp_meta,
    })


#####################################################################################################################
##collaborator

# ================== MONGODB ATLAS ==================
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["narmada_project"]
collaborators = db["collaborators"]

# ================== COLLABORATOR LOGIN + REGISTER ==================
@app.route("/collaborator/login", methods=["GET", "POST"])
def collaborator_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")
        action = request.form.get("action")

        user = collaborators.find_one({"email": email})

        # -------- REGISTER --------
        if action == "register":
            if user:
                return render_template("collaborator/login.html", error="User already exists")

            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

            new_user = collaborators.insert_one({
                "email": email,
                "password": hashed
            })

            # 🔥 GET COLLAB ID
            collab_id = str(new_user.inserted_id)

            # 🔥 CREATE FOLDER STRUCTURE
            base_path = os.path.join(BASE_DIR, "data", "collaborator", collab_id)

            os.makedirs(os.path.join(base_path, "display"), exist_ok=True)
            os.makedirs(os.path.join(base_path,"gnn" , "training_input"), exist_ok=True)
            os.makedirs(os.path.join(base_path, "gnn", "testing_input"), exist_ok=True)

            print(f"✅ Folders created for {collab_id}")

            return render_template(
                "collaborator/login.html",
                success="Registered successfully"
            )

        # -------- LOGIN --------
        elif action == "login":
            if not user:
                return render_template("collaborator/login.html", error="User not found")

            if bcrypt.checkpw(password.encode(), user["password"]):

                # 🔥 STORE SESSION
                session["collab_id"] = str(user["_id"])
                session["collab_email"] = user["email"]

                return redirect("/collaborator/home")
            else:
                return render_template("collaborator/login.html", error="Invalid password")

    return render_template("collaborator/login.html")


# ================== COLLABORATOR HOME ==================
@app.route("/collaborator/home")
def collaborator_home():

    if "collab_id" not in session:
        return redirect("/collaborator/login")

    return render_template("collaborator/home.html")



# ================== LOGOUT ==================
@app.route("/collaborator/logout")
def collaborator_logout():
    session.pop('collab_id',None)
    return redirect("/collaborator/login")

@app.route("/collaborator/display")
def collaborator_display():
    if "collab_id" not in session:
     return redirect("/collaborator/login")
    return send_from_directory(os.path.join(BASE_DIR, "template","collaborator"), "display.html")

@app.route("/collaborator/output")
def collaborator_output():
    if "collab_id" not in session:
        return redirect("/collaborator/login")
    return send_from_directory(os.path.join(BASE_DIR, "template", "collaborator"), "output.html")


@app.route("/collaborator/clear/display", methods=["POST"])
def collaborator_clear_display():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "collaborator", session["collab_id"], "display")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Display directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/collaborator/clear/training", methods=["POST"])
def collaborator_clear_training():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "collaborator", session["collab_id"], "gnn", "training_input")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Training directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/collaborator/clear/testing", methods=["POST"])
def collaborator_clear_testing():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        folder_path = os.path.join(BASE_DIR, "data", "collaborator", session["collab_id"], "gnn", "testing_input")
        clear_directory_contents(folder_path)
        return jsonify({"message": "Testing directory cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/collaborator/upload/display")
def collaborator_upload_display():
    if "collab_id" not in session:
     return redirect("/collaborator/login")
    return send_from_directory(os.path.join(BASE_DIR, "template","collaborator"), "upload_display.html")

@app.route("/collaborator/upload/training")
def collaborator_upload_training():
     if "collab_id" not in session:
      return redirect("/collaborator/login")
     return send_from_directory(os.path.join(BASE_DIR, "template","collaborator"), "upload_training.html")

@app.route("/collaborator/upload/testing")
def collaborator_upload_testing():
     if "collab_id" not in session:
      return redirect("/collaborator/login")
     return send_from_directory(os.path.join(BASE_DIR, "template","collaborator"), "upload_testing.html")
    

@app.route("/api/collaborator/upload/stations", methods=["GET", "POST"])
def collaborator_upload_stations():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "No file provided"}), 400
        if not file.filename.endswith(".csv"):
            return jsonify({"error": "Only CSV files are accepted"}), 400

        save_dir = os.path.join(BASE_DIR, "data", "collaborator", session["collab_id"], "gnn")
        os.makedirs(save_dir, exist_ok=True)
        file.save(os.path.join(save_dir, "upstream_to_downstream_stations.csv"))
        return jsonify({"message": "Station topology uploaded successfully"}), 200

    return jsonify({"error": "Method not allowed"}), 405

@app.route("/runcol", methods=["GET", "POST"])
def run_collaborator_gnn_pipeline():
    if "collab_id" not in session:
        if request.method == "POST":
            return jsonify({"error": "Unauthorized"}), 401
        return render_template("collaborator/login.html", error="You are not Authorised . Login First ")
    collab_id=session['collab_id']
    scripts_dir = os.path.join(BASE_DIR, "data", "collaborator", "gnn")
    collab_gnn_dir = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "gnn")
    required_streamflow_dir = os.path.join(collab_gnn_dir, "training_input", "streamflow")

    if not os.path.exists(required_streamflow_dir):
        return jsonify({
            "error": "Missing collaborator training streamflow data",
            "details": f"Upload training CSV files first. Expected folder: {required_streamflow_dir}"
        }), 400

    ordered_scripts = [
        "app.py",
        "app_testing.py",
        "gnn_training.py",
        "gnn_testing.py",
        "generate_rasters.py",
    ]

    candidate_pythons = [
    os.path.join(BASE_DIR, "data", "admin", "gnn", "venv", "bin", "python"),
    os.path.join(BASE_DIR, "data", "admin", "gnn", "venv", "Scripts", "python.exe"),
    os.path.join(scripts_dir, "venv", "bin", "python"),
    os.path.join(scripts_dir, "venv", "Scripts", "python.exe"),
    os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe"),
    os.path.join(BASE_DIR, ".venv", "bin", "python"),
    sys.executable,
]

    python_cmd = None
    for candidate in candidate_pythons:
        if not os.path.exists(candidate):
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "import torch"],
                capture_output=True,
                text=True,
            )
        except OSError:
            # Skip incompatible executables (e.g., Windows python.exe from Linux/WSL).
            continue
        if probe.returncode == 0:
            python_cmd = candidate
            break

    if python_cmd is None:
        return jsonify({
            "error": "No Python environment with torch found for collaborator pipeline",
            "details": "Install torch in data/collaborator/gnn/venv or data/admin/gnn/venv."
        }), 500

    try:
        for script_name in ordered_scripts:
            script_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(script_path):
                return jsonify({"error": f"Missing script: {script_path}"}), 404

            completed = subprocess.run(
                [python_cmd, script_path,collab_id],
                check=True,
                cwd=scripts_dir,
                capture_output=True,
                text=True,
            )

            if completed.stdout:
                print(completed.stdout)

        output_url = "/collaborator/output"
        if request.method == "POST":
            return jsonify({"message": "Pipeline completed", "redirect": output_url}), 200
        return jsonify({"message": "Pipeline completed", "redirect": output_url}), 200
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        details = stderr if stderr else stdout
        return jsonify({
            "error": f"Pipeline failed at {e.cmd}",
            "details": details or str(e)
        }), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


       

@app.route("/api/collaborator-upload-testing-data", methods=["POST"])
def collaborator_upload_testing_data():
    if "collab_id" not in session:
         return render_template("collaborator/login.html", error="You are not Authorised . Login First ")
    try:
        file = request.files.get("file")
        upload_type = (request.form.get("upload_type") or "csv").strip().lower()
        collab_id = session["collab_id"]

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        type_config = {
            "csv": {
                "extension": ".csv",
                "folder": os.path.join(BASE_DIR, "data", "collaborator", collab_id, "gnn", "testing_input")
            },
            "lulc": {
                "extension": ".tif",
                "folder": os.path.join(BASE_DIR, "data", "collaborator", collab_id, "gnn", "testing_input", "lulc")
            },
            "pop": {
                "extension": ".tif",
                "folder": os.path.join(BASE_DIR, "data", "collaborator", collab_id, "gnn", "testing_input", "pop")
            }
        }

        if upload_type not in type_config:
            return jsonify({"error": "Invalid upload type"}), 400

        expected_ext = type_config[upload_type]["extension"]
        if not file.filename.lower().endswith(expected_ext):
            return jsonify({"error": f"Only {expected_ext} files allowed for {upload_type}"}), 400

        upload_folder = type_config[upload_type]["folder"]
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)

        file.save(file_path)

        return jsonify({
            "message": f"Testing {upload_type} uploaded successfully",
            "file_path": file_path
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/collaborator-update-stations-display", methods=["POST"])
def collaborator_update_all_stations_display():

    if "collab_id" not in session:
        return redirect("/collaborator/login")

    try:
        year = int(request.form.get("year"))
        month_input = request.form.get("month")
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        df = pd.read_csv(file)

        if "station" not in df.columns:
            return jsonify({"error": "Missing 'station' column"}), 400

        df.set_index("station", inplace=True)

        collab_id = session["collab_id"]
        BASE = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display")

        month_map = {
            "1": "Jan", "2": "Feb", "3": "Mar",
            "4": "Apr", "5": "May", "6": "Jun",
            "7": "Jul", "8": "Aug", "9": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }
        month = month_map.get(str(month_input), month_input)

        updated = []

        # ---------- STREAMFLOW ----------
        sf_path = os.path.join(BASE, "streamflow", "Streamflow_monthly_1.csv")
        os.makedirs(os.path.dirname(sf_path), exist_ok=True)

        if os.path.exists(sf_path):
            sf_df = pd.read_csv(sf_path)
        else:
            sf_df = pd.DataFrame(columns=["Station","Year","Month","Value","Latitude","Longitude"])

        # ---------- WATER LEVEL ----------
        wl_path = os.path.join(BASE, "waterlevel", "water_level_monthly.csv")
        os.makedirs(os.path.dirname(wl_path), exist_ok=True)

        if os.path.exists(wl_path):
            wl_df = pd.read_csv(wl_path)
        else:
            wl_df = pd.DataFrame(columns=["Station","Year","Month","Value","Latitude","Longitude"])

        # ---------- LOOP ----------
        for station in df.index:

            station_file = station if station.startswith("Station_") else station.split("_")[0]

            # ---------- PRECIP ----------
            if "precip" in df.columns:
                val = df.loc[station, "precip"]

                if not pd.isna(val):
                    path = os.path.join(BASE, "precip", f"{station}.csv")
                    os.makedirs(os.path.dirname(path), exist_ok=True)

                    if os.path.exists(path):
                        station_df = pd.read_csv(path)
                    else:
                        station_df = pd.DataFrame(columns=["Year","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                    mask = station_df["Year"] == year if not station_df.empty else []

                    if len(mask) > 0 and any(mask):
                        station_df.loc[mask, month] = val
                    else:
                        new_row = {col: None for col in station_df.columns}
                        new_row["Year"] = year
                        new_row[month] = val
                        station_df = pd.concat([station_df, pd.DataFrame([new_row])], ignore_index=True)

                    station_df.to_csv(path, index=False)

            # ---------- STREAMFLOW ----------
            if "streamflow" in df.columns:
                val = df.loc[station, "streamflow"]

                if not pd.isna(val):
                    mask = (
                        (sf_df["Station"] == station_file) &
                        (sf_df["Year"] == year) &
                        (sf_df["Month"] == month)
                    ) 

                    if mask.any():
                        sf_df.loc[mask, "Value"] = val
                    else:
                        sf_df = pd.concat([sf_df, pd.DataFrame([{
                            "Station": station_file,
                            "Year": year,
                            "Month": month,
                            "Value": val,
                            "Latitude": None,
                            "Longitude": None
                        }])], ignore_index=True)

            # ---------- WATER LEVEL ----------
            if "waterlevel" in df.columns:
                val = df.loc[station, "waterlevel"]

                if not pd.isna(val):
                    mask = (
                        (wl_df["Station"] == station_file) &
                        (wl_df["Year"] == year) &
                        (wl_df["Month"] == month)
                    )

                    if mask.any():
                        wl_df.loc[mask, "Value"] = val
                    else:
                        wl_df = pd.concat([wl_df, pd.DataFrame([{
                            "Station": station_file,
                            "Year": year,
                            "Month": month,
                            "Value": val,
                            "Latitude": None,
                            "Longitude": None
                        }])], ignore_index=True)

            updated.append(station)

        sf_df.to_csv(sf_path, index=False)
        wl_df.to_csv(wl_path, index=False)

        return jsonify({"message": "Training updated", "stations": updated}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/get-collab-id")
def get_collab_id():
    if "collab_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    return jsonify({
        "collab_id": session["collab_id"]
    })


# =========================
# UPLOAD-ALL  (All 8 GeoJSONs)
# =========================
@app.route("/collaborator/display/upload-all", methods=["POST"])
def upload_all_display():
    try:
        collab_id = session.get("collab_id")
        if not collab_id:
            return jsonify({"error": "Not logged in"}), 401

        print("Collab ID:", collab_id)

        upload_folder = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display", "geojson")

        # ✅ CREATE FOLDER (FIX)
        os.makedirs(upload_folder, exist_ok=True)

        geojson_key_map = {
            "state_boundary":        "state_boundary.geojson",
            "district_boundary":     "district_boundary.geojson",
            "state_hq":              "state_hq.geojson",
            "district_hq":           "district_hq.geojson",
            "major_towns":           "major_towns.geojson",
            "narmada_polygon":       "narmada.geojson",
            "narmada_centerline":    "narmada_centerline.geojson",
            "narmada_named_network": "narmada_named_network.geojson",
        }

        saved = []

        for form_key, save_filename in geojson_key_map.items():
            if form_key in request.files:
                file = request.files[form_key]

                if file.filename == "":
                    continue

                save_path = os.path.join(upload_folder, save_filename)

                # ✅ DEBUG LOG
                print("Saving to:", save_path)

                file.save(save_path)
                saved.append(form_key)

        return jsonify({
            "message": f"GeoJSONs saved successfully ✅",
            "saved": saved
        }), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# =========================
# UPLOAD-CHUNK  (Rasters & CSVs)
# =========================
DATA_DIR = os.path.join(BASE_DIR, "data")

# @app.route("/collaborator/display/upload-chunk", methods=["POST"])
# def upload_chunk_display():
#     try:
#         collab_id = session.get("collab_id")
#         if not collab_id:
#             return jsonify({"error": "Not logged in"}), 401

#         file = request.files.get("file")
#         filename = secure_filename(request.form.get("filename", ""))
#         chunk_index = int(request.form.get("chunkIndex", 0))
#         total_chunks = int(request.form.get("totalChunks", 1))
#         file_category = (request.form.get("fileCategory", "") or "").strip().lower()
#         field_name = request.form.get("fieldName", "")

#         if not file or not filename:
#             return jsonify({"error": "Missing file data"}), 400

#         base_folder = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display")
#         os.makedirs(base_folder, exist_ok=True)
#         temp_dir = os.path.join(base_folder, "temp_chunks")
#         os.makedirs(temp_dir, exist_ok=True)
      

#         # Raster rename
#         raster_map = {
#             "precip_raster": "precip_raster.tif",
#             "temp_raster": "temp_raster.tif",
#             "lulc_raster": "lulc_raster.tif",
#             "pop_raster": "pop_raster.tif",
#         }

#         if file_category == "raster" and field_name in raster_map:
#             filename = raster_map[field_name]

#         chunk_path = os.path.join(temp_dir, f"{filename}.part{chunk_index}")
#         file.save(chunk_path)

#         if chunk_index == total_chunks - 1:

#             category_to_dir = {
#                 "precip": os.path.join(base_folder, "precip"),
#                 "temp": os.path.join(base_folder, "temp"),
#                 "streamflow": os.path.join(base_folder, "streamflow"),
#                 "waterlevel": os.path.join(base_folder, "waterlevel"),
#                 "lulc_raster": os.path.join(base_folder, "raster", "lulc"),
#                 "pop_raster": os.path.join(base_folder, "raster", "pop"),
#                 "raster": os.path.join(base_folder, "raster"),
#             }
#             dest_dir = category_to_dir.get(file_category, base_folder)

#             base_abs = os.path.abspath(base_folder)
#             dest_abs = os.path.abspath(dest_dir)
#             if not dest_abs.startswith(base_abs + os.sep) and dest_abs != base_abs:
#                 return jsonify({"error": "Invalid upload destination"}), 400

#             os.makedirs(dest_dir, exist_ok=True)
#             final_path = os.path.join(dest_dir, filename)

#             with open(final_path, "wb") as out:
#                 for i in range(total_chunks):
#                     part = os.path.join(temp_dir, f"{filename}.part{i}")
#                     with open(part, "rb") as p:
#                         out.write(p.read())
#                     os.remove(part)

#             print(f"✅ Saved → {final_path} (category={file_category})")

#             return jsonify({"message": "File uploaded"}), 200

#         return jsonify({"message": "Chunk uploaded"}), 200

#     except Exception as e:
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

 
@app.route("/collaborator/display/upload-chunk", methods=["POST"])
def upload_chunk_display():
    try:
        collab_id = session.get("collab_id")
        if not collab_id:
            return jsonify({"error": "Not logged in"}), 401
 
        file          = request.files.get("file")
        filename      = secure_filename(request.form.get("filename", ""))
        chunk_index   = int(request.form.get("chunkIndex", 0))
        total_chunks  = int(request.form.get("totalChunks", 1))
        file_category = (request.form.get("fileCategory", "") or "").strip().lower()
        field_name    = request.form.get("fieldName", "")
 
        if not file or not filename:
            return jsonify({"error": "Missing file data"}), 400
 
        base_folder = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display")
        os.makedirs(base_folder, exist_ok=True)
        temp_dir = os.path.join(base_folder, "temp_chunks")
        os.makedirs(temp_dir, exist_ok=True)
 
        # Raster rename map
        raster_map = {
            "precip_raster": "precip_raster.tif",
            "temp_raster":   "temp_raster.tif",
            "lulc_raster":   "lulc_raster.tif",
            "pop_raster":    "pop_raster.tif",
        }
        if file_category == "raster" and field_name in raster_map:
            filename = raster_map[field_name]
 
        chunk_path = os.path.join(temp_dir, f"{filename}.part{chunk_index}")
        file.save(chunk_path)
 
        if chunk_index == total_chunks - 1:
            category_to_dir = {
                "precip":     os.path.join(base_folder, "precip"),
                "temp":       os.path.join(base_folder, "temp"),
                "streamflow": os.path.join(base_folder, "streamflow"),
                "waterlevel": os.path.join(base_folder, "waterlevel"),
                "lulc_raster": os.path.join(base_folder, "raster", "lulc"),
                "pop_raster":  os.path.join(base_folder, "raster", "pop"),
                "raster":      os.path.join(base_folder, "raster"),
            }
            dest_dir = category_to_dir.get(file_category, base_folder)
 
            base_abs = os.path.abspath(base_folder)
            dest_abs = os.path.abspath(dest_dir)
            if not dest_abs.startswith(base_abs + os.sep) and dest_abs != base_abs:
                return jsonify({"error": "Invalid upload destination"}), 400
 
            os.makedirs(dest_dir, exist_ok=True)
            final_path = os.path.join(dest_dir, filename)
 
            with open(final_path, "wb") as out:
                for i in range(total_chunks):
                    part = os.path.join(temp_dir, f"{filename}.part{i}")
                    with open(part, "rb") as p:
                        out.write(p.read())
                    os.remove(part)
 
            print(f"✅ Saved → {final_path} (category={file_category})")
            return jsonify({"message": "File uploaded"}), 200
 
        return jsonify({"message": "Chunk uploaded"}), 200
 
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/collaborator/display/shp", methods=["POST"])
def upload_shp_display():
    try:
        collab_id = session.get("collab_id")
        if not collab_id:
            return jsonify({"error": "Not logged in"}), 401
 
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file provided"}), 400
 
        # Force the saved filename regardless of what the browser sends
        saved_name = "narmada_buffer_1000m.shp"
 
        # Validate extension
        original_name = secure_filename(file.filename or "")
        if not original_name.lower().endswith(".shp"):
            return jsonify({"error": "Only .shp files are accepted"}), 400
 
        base_folder = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display")
        shp_dir     = os.path.join(base_folder, "shp")
 
        # Path traversal guard
        base_abs = os.path.abspath(base_folder)
        shp_abs  = os.path.abspath(shp_dir)
        if not shp_abs.startswith(base_abs + os.sep) and shp_abs != base_abs:
            return jsonify({"error": "Invalid upload destination"}), 400
 
        os.makedirs(shp_dir, exist_ok=True)
        final_path = os.path.join(shp_dir, saved_name)
        file.save(final_path)
 
        print(f"✅ Shapefile saved → {final_path}")
        return jsonify({"message": "Shapefile uploaded", "path": final_path}), 200
 
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/collaborator/training/upload-chunk", methods=["POST"])
def upload_chunk_training():
    try:
        collab_id = session.get("collab_id")
        if not collab_id:
            return jsonify({"error": "Not logged in"}), 401

        file = request.files.get("file")
        filename = secure_filename(request.form.get("filename", ""))
        chunk_index = int(request.form.get("chunkIndex", 0))
        total_chunks = int(request.form.get("totalChunks", 1))
        file_category = request.form.get("fileCategory", "")
        field_name = request.form.get("fieldName", "")

        base_folder = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "gnn", "training_input")
     
        temp_dir = os.path.join(base_folder, "temp_chunks")
        os.makedirs(temp_dir, exist_ok=True)
        print(collab_id)
        chunk_path = os.path.join(temp_dir, f"{filename}.part{chunk_index}")
        file.save(chunk_path)

        if chunk_index == total_chunks - 1:

            if file_category == "precip":
                dest = os.path.join(base_folder, "precip")
            elif file_category == "temp":
                dest = os.path.join(base_folder, "temp")
            elif file_category == "streamflow":
                dest = os.path.join(base_folder, "streamflow")
            elif file_category == "waterlevel":
                dest = os.path.join(base_folder, "waterlevel")
            elif file_category == "lulc_raster":
                dest = os.path.join(base_folder, "raster", "lulc")
            elif file_category == "pop_raster":
                dest = os.path.join(base_folder, "raster","pop")
            elif file_category == "raster":
                dest = os.path.join(base_folder, "raster")
            else:
                dest = base_folder

            os.makedirs(dest, exist_ok=True)
            final_path = os.path.join(dest, filename)

            with open(final_path, "wb") as f:
                for i in range(total_chunks):
                    part = os.path.join(temp_dir, f"{filename}.part{i}")
                    with open(part, "rb") as p:
                        f.write(p.read())
                    os.remove(part)

            print(f"✅ Training saved → {final_path}")

            return jsonify({"message": "Training file uploaded"}), 200

        return jsonify({"message": "Chunk uploaded"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/collaborator/testing/upload-chunk", methods=["POST"])
def upload_chunk_testing():
    try:
        collab_id = session.get("collab_id")
        if not collab_id:
            return jsonify({"error": "Not logged in"}), 401

        file = request.files.get("file")
        filename = secure_filename(request.form.get("filename", ""))
        chunk_index = int(request.form.get("chunkIndex", 0))
        total_chunks = int(request.form.get("totalChunks", 1))
        file_category = request.form.get("fileCategory", "")

        base_folder = os.path.join(BASE_DIR, "data", "collaborator",collab_id, "gnn", "testing_input")

        temp_dir = os.path.join(base_folder, "temp_chunks")
        os.makedirs(temp_dir, exist_ok=True)

        chunk_path = os.path.join(temp_dir, f"{filename}.part{chunk_index}")
        file.save(chunk_path)

        if chunk_index == total_chunks - 1:

            if file_category == "precip":
                dest = os.path.join(base_folder, "precip")
            elif file_category == "temp":
                dest = os.path.join(base_folder, "temp")
            elif file_category == "streamflow":
                dest = os.path.join(base_folder, "streamflow")
            elif file_category == "waterlevel":
                dest = os.path.join(base_folder, "waterlevel")
            elif file_category == "lulc_raster":
                dest = os.path.join(base_folder, "raster", "lulc")
            elif file_category == "pop_raster":
                dest = os.path.join(base_folder, "raster","pop")
            elif file_category == "raster":
                dest = os.path.join(base_folder, "raster")
            else:
                dest = base_folder

            os.makedirs(dest, exist_ok=True)
            final_path = os.path.join(dest, filename)

            with open(final_path, "wb") as f:
                for i in range(total_chunks):
                    part = os.path.join(temp_dir, f"{filename}.part{i}")
                    with open(part, "rb") as p:
                        f.write(p.read())
                    os.remove(part)

            print(f"✅ Testing saved → {final_path}")

            return jsonify({"message": "Testing file uploaded"}), 200

        return jsonify({"message": "Chunk uploaded"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




@app.route("/api/collaborator-clip-precip")
def collaborator_clip_precip():
    try:
        collaborator_clip_precipitation_raster(session["collab_id"])
        return jsonify({"message": "Precipitation raster clipped successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/api/collaborator-clip-temperature")
def collaborator_clip_temperature():
    try:
        collaborator_clip_temperature_raster(session["collab_id"])
        return jsonify({"message": "Mean temperature raster clipped successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/collaborator-generate-precip-year")
def collaborator_generate_precip_year():
    try:
        year = request.args.get("year", type=int)

        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for year {year}...")

        script_path =os.path.join(BASE_DIR, "scripts", "collaborator_interpolation_precp.py")

       
        subprocess.run(
            ["python3", script_path, str(year),session["collab_id"]],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "collaborator",
            session["collab_id"],
            "display",
            "precip",
            "output_precip_rasters",
            f"precip_{year}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/collaborator/{session["collab_id"]}/display/precip/output_precip_rasters/precip_{year}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/collaborator-generate-temp-year")
def collaborator_generate_temp_year():
    try:
        year = request.args.get("year", type=int)

        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for year {year}...")

        script_path =os.path.join(BASE_DIR, "scripts", "collaborator_interpolation_temp.py")

       
        subprocess.run(
            ["python3", script_path, str(year),session["collab_id"]],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "collaborator",
            session["collab_id"],
            "display",
            "precip",
            "output_temp_rasters",
            f"precip_{year}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/collaborator/{session["collab_id"]}/display/temp/output_temp_rasters/precip_{year}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/collaborator-generate-streamflow-year")
def collaborator_generate_streamflow_year():
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=str)
        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for {year , month}...")

        script_path =os.path.join(BASE_DIR, "scripts", "collaborator_interpolation_stream_flow.py")

       
        subprocess.run(
            ["python3", script_path, str(year),month,session["collab_id"]],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "collaborator",
            session["collab_id"],
            "display",
            "streamflow",
            "output_streamflow_rasters",
            f"streamflow_{year}_{month}_30m.tif"
        )

       
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year , month}",
            "file": f"data/collaborator/{session["collab_id"]}/display/streamflow/output_streamflow_rasters/streamflow_{year}_{month}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/collaborator-generate-waterlevel-year")
def collaborator_generate_waterlevel_year():
    try:
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=str)
        if year is None:
            return jsonify({"error": "Year required"}), 400

        print(f" Generating raster for {year , month}...")

        script_path =os.path.join(BASE_DIR, "scripts", "collaborator_interpolation_water_level.py")

       
        subprocess.run(
            ["python3", script_path, str(year),month,session["collab_id"]],
            check=True
        )

        
        raster_path = os.path.join(
            BASE_DIR,
            "data",
            "collaborator",
            session["collab_id"],
            "display",
            "waterlevel",
            "output_waterlevel_rasters",
            f"waterlevel_{year}_{month}_30m.tif"
        )

        
        if not os.path.exists(raster_path):
            return jsonify({"error": "Raster not generated"}), 500

        print(f"Raster ready: {raster_path}")

      
        return jsonify({
            "message": f"Raster generated for {year}",
            "file": f"data/collaborator/{session["collab_id"]}/display/waterlevel/output_waterlevel_rasters/waterlevel_{year}_{month}_30m.tif"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

import re

@app.route("/api/collaborator-get-years/<dataset>")
def get_years(dataset):

    base_path = os.path.join(BASE_DIR, "data", "collaborator", session["collab_id"], "display")

    try:

        # ===============================
        # ✅ LULC & POP (RASTER)
        # ===============================
        if dataset in ["lulc", "pop"]:

            folder = os.path.join(base_path, "raster",dataset)

            if not os.path.exists(folder):
                return jsonify([])

            years = set()

            for file in os.listdir(folder):

                if not file.endswith(".tif"):
                    continue

                # 🔥 Extract year using regex (robust)
                import re
                match = re.search(r"(19|20)\d{2}", file)

                if match:
                    years.add(int(match.group()))

            return jsonify(sorted(years))


        # ======================================
        # ✅ CSV DATA (COLUMN-BASED YEARS)
        # ======================================
        else:

            folder_map = {
                "precip": "precip",
                "temp": "temp",
                "streamflow": "streamflow",
                "waterlevel": "waterlevel"
            }

            folder = os.path.join(base_path, folder_map.get(dataset, ""))

            if not os.path.exists(folder):
                return jsonify([])

            csv_files = [
                f for f in os.listdir(folder)
                if f.endswith(".csv") and not f.lower().startswith("sample")
            ]

            if not csv_files:
                return jsonify([])

            years = set()

            for csv_name in csv_files:
                csv_path = os.path.join(folder, csv_name)

                try:
                    header_cols = pd.read_csv(csv_path, nrows=0).columns.tolist()
                    if not header_cols:
                        continue

                    year_col = next(
                        (c for c in header_cols if str(c).strip().lower() == "year"),
                        header_cols[0]
                    )

                    df = pd.read_csv(csv_path, usecols=[year_col])
                    numeric_years = pd.to_numeric(df[year_col], errors="coerce").dropna().astype(int)

                    for y in numeric_years:
                        if 1800 < y < 3000:
                            years.add(int(y))
                except Exception:
                    continue

            return jsonify(sorted(list(years)))


    except Exception as e:
        print("Year detection error:", e)
        return jsonify([])


@app.route("/api/collaborator-raster-range-meta", methods=["GET"])
def collaborator_raster_range_meta():
    if "collab_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    collab_id = session["collab_id"]
    raster_dir = os.path.join(BASE_DIR, "data", "collaborator", collab_id, "display", "raster")

    def pick_file(kind):
        if not os.path.exists(raster_dir):
            return None

        candidates = []
        for fname in os.listdir(raster_dir):
            lower = fname.lower()
            if not lower.endswith(".tif"):
                continue
            if "clipped" in lower:
                continue

            if kind == "precip":
                if "precip" not in lower and "precipiration" not in lower:
                    continue
            elif kind == "temp":
                if "temp" not in lower and "temperature" not in lower:
                    continue

            import re
            match = re.match(r"^((?:19|20)\d{2})_((?:19|20)\d{2})_(.+)\.tif$", fname)
            if not match:
                continue

            start_year = int(match.group(1))
            end_year = int(match.group(2))
            candidates.append((start_year, end_year, fname))

        if not candidates:
            return None

        start_year, end_year, selected = sorted(candidates, key=lambda x: (x[0], x[1]))[-1]
        return {
            "file": selected,
            "startYear": start_year,
            "endYear": end_year,
        }

    return jsonify({
        "precip": pick_file("precip"),
        "temp": pick_file("temp"),
    })

#####################################################################################################################

@app.route("/<path:filename>",methods=["GET"])
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
