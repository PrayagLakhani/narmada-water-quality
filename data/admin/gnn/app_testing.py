import os
import pandas as pd
import numpy as np
import json
import rasterio
from rasterio.mask import mask

# =========================
# BASE DIR
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))



INPUT_DIR = os.path.join(BASE_DIR, "testing_input")
OUTPUT_DIR = os.path.join(BASE_DIR, "testing_gnn","year_month_files")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# raster folders
lulc_dir = os.path.join(INPUT_DIR, "lulc")
pop_dir = os.path.join(INPUT_DIR, "pop")

# =========================
# LOAD NORMALIZATION PARAMS
# =========================
with open(os.path.join(BASE_DIR, "norm_params.json"), "r") as f:
    norm_params = json.load(f)

# =========================
# NORMALIZE
# =========================
def normalize(val, vmin, vmax):
    if vmax == vmin:
        return np.zeros_like(val)
    return (val - vmin) / (vmax - vmin)

# =========================
# PROCESS FILES (DEFINE FIRST)
# =========================
files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".csv")]

# =========================
# LULC MAPPING (EXACT SAME)
# =========================
apc_mapping = {
    14: 0.9, 15: 0.9,
    13: 0.7,
    11: 0.6,
    12: 0.4,
    16: 0.2,
    0: 0.0, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05,
    5: 0.05, 6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
    17: 0.0
}

built_classes = [14, 15]
vegetation_classes = [0,1,2,3,4,5,6,7,8,9,10]

# =========================
# POPULATION MEAN (GLOBAL)
# =========================
all_pop_values = []
for pf in os.listdir(pop_dir):
    if not pf.endswith(".tif"):
        continue

    with rasterio.open(os.path.join(pop_dir, pf)) as src:
        band = src.read(1)
        vals = band.flatten()
        vals = vals[~np.isnan(vals)]
        vals = vals[vals > 0]
        all_pop_values.extend(vals)

rho_mean_basin = np.mean(all_pop_values)

# =========================
# PRECIP MONTHLY MEAN (FIXED)
# =========================
month_means = {}

for f in files:
    df_temp = pd.read_csv(os.path.join(INPUT_DIR, f))
    year_str, mstr = f.replace(".csv", "").split("_")

    month_map = {
        "Jan":0,"Feb":1,"Mar":2,"Apr":3,"May":4,"Jun":5,
        "Jul":6,"Aug":7,"Sep":8,"Oct":9,"Nov":10,"Dec":11
    }

    m = month_map[mstr]
    vals = df_temp["precip"].values.astype(float)
    vals = vals[~np.isnan(vals)]

    if len(vals) > 0:
        month_means.setdefault(m, []).extend(vals)

for m in month_means:
    month_means[m] = np.mean(month_means[m])

print("Monthly mean precipitation:", month_means)

# =========================
# MAIN LOOP
# =========================
for file in files:

    print(f"\nProcessing {file}")

    df = pd.read_csv(os.path.join(INPUT_DIR, file))

    # extract lat lon from station
    lons, lats = [], []
    for s in df["station"]:
        lon, lat = map(float, s.split("_"))
        lons.append(lon)
        lats.append(lat)

    df["lon"] = lons
    df["lat"] = lats

    # =========================
    # EXTRACT YEAR & MONTH FROM FILE NAME
    # =========================
    name = file.replace(".csv", "")
    year_str, month_str = name.split("_")

    year = int(year_str)

    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }

    month = month_map[month_str]
    month_index = np.full(len(df), month - 1)

    # =========================
    # STREAMFLOW
    # =========================
    Q = df["streamflow"].values.astype(float)

    dci_vals = Q / norm_params["Q_mean_basin"]

    lfsf = np.where(np.isnan(Q), np.nan,
                    np.where(Q < norm_params["Q10"], 1, 0))

    with np.errstate(divide='ignore', invalid='ignore'):
        plaf_vals = 1 / dci_vals

    plaf_vals[np.isinf(plaf_vals)] = np.nan

    dci = normalize(dci_vals, norm_params["dci_min"], norm_params["dci_max"])
    plaf = normalize(plaf_vals, norm_params["plaf_min"], norm_params["plaf_max"])

    # =========================
    # WATER LEVEL
    # =========================
    H = df["waterlevel"].values.astype(float)
    ri = (norm_params["H_mean"] - H) / norm_params["H_mean"]
    ri = normalize(ri, norm_params["ri_min"], norm_params["ri_max"])

    # =========================
    # TEMPERATURE
    # =========================
    Tmax = df["maxt"].values.astype(float)
    Tmin = df["mint"].values.astype(float)

    tsi = (Tmax - norm_params["T_threshold"]) / norm_params["T_threshold"]

    with np.errstate(divide='ignore', invalid='ignore'):
        DO_sat = 468 / (31.6 + Tmax)

    DO_sat_max = 468 / (31.6 + 0)
    tddf = DO_sat / DO_sat_max

    dss = Tmax - Tmin

    tsi = normalize(tsi, norm_params["tsi_min"], norm_params["tsi_max"])
    tddf = normalize(tddf, norm_params["tddf_min"], norm_params["tddf_max"])
    dss = normalize(dss, norm_params["dss_min"], norm_params["dss_max"])

    # =========================
    # POPULATION
    # =========================
    L_percapita = 135.0
    T_coverage = 0.3

    dpli_vals = []
    sgp_vals = []
    
    with rasterio.open(os.path.join(pop_dir, f"{year}.tif")) as src:
        band = src.read(1)
        nodata = src.nodata

        for i in range(len(df)):
            try:
                row, col = src.index(df["lon"][i], df["lat"][i])
                rho = band[row, col]
            except:
                rho = np.nan

            if nodata is not None and rho == nodata:
                rho = np.nan

            if np.isnan(rho) or rho <= 0:
                rho = rho_mean_basin

            dpli_vals.append(rho / rho_mean_basin)
            sgp_vals.append(rho * L_percapita * (1 - T_coverage))

    dpli = normalize(np.array(dpli_vals), norm_params["dpli_min"], norm_params["dpli_max"])
    sgp = normalize(np.array(sgp_vals), norm_params["sgp_min"], norm_params["sgp_max"])
    # =========================
    # LULC (UPDATED - MATCH SECOND CODE LOGIC)
    # =========================
    clpi_vals, isf_vals, fv_raw_vals = [], [], []

    raster_path = os.path.join(lulc_dir, f"{year}.tif")

    with rasterio.open(raster_path) as src:
        for i in range(len(df)):

            lon = df["lon"][i]
            lat = df["lat"][i]

            geom = {
                "type": "Polygon",
                "coordinates": [[
                    [lon-0.01, lat-0.01],
                    [lon+0.01, lat-0.01],
                    [lon+0.01, lat+0.01],
                    [lon-0.01, lat+0.01],
                    [lon-0.01, lat-0.01]
                ]]
            }

            try:
                img, _ = mask(src, [geom], crop=True)
                band = img[0]

                nodata = src.nodata
                if nodata is not None:
                    band = band[band != nodata]

                band = band[~np.isnan(band)]

                if len(band) == 0:
                    clpi_vals.append(0.3)
                    isf_vals.append(0.1)
                    fv_raw_vals.append(0.5)
                    continue

                apc_vals = np.array([apc_mapping.get(int(round(v)), 0.3) for v in band])

                clpi_vals.append(np.mean(apc_vals))
                isf_vals.append(np.sum(np.isin(np.round(band).astype(int), built_classes)) / len(band))
                fv_raw_vals.append(np.sum(np.isin(np.round(band).astype(int), vegetation_classes)) / len(band))

            except:
                clpi_vals.append(0.3)
                isf_vals.append(0.1)
                fv_raw_vals.append(0.5)

    clpi = normalize(np.array(clpi_vals), norm_params["clpi_min"], norm_params["clpi_max"])
    isf = normalize(np.array(isf_vals), norm_params["isf_min"], norm_params["isf_max"])
    fv = normalize(np.array(fv_raw_vals), norm_params["fv_min"], norm_params["fv_max"])

    # =========================
    # PRECIP (FIXED)
    # =========================
    P = df["precip"].values.astype(float)

    rdf_vals, rpi_vals, season_vals = [], [], []

    month_to_season = {
        0: "Winter", 1: "Winter",
        2: "Pre-monsoon", 3: "Pre-monsoon", 4: "Pre-monsoon",
        5: "Monsoon", 6: "Monsoon", 7: "Monsoon", 8: "Monsoon",
        9: "Post-monsoon", 10: "Post-monsoon",
        11: "Winter"
    }

    for i in range(len(P)):
        p = P[i]
        m = month_index[i]

        if np.isnan(p):
            rdf_vals.append(np.nan)
            rpi_vals.append(np.nan)
            season_vals.append(None)
            continue

        mm = month_means[m]

        rdf_vals.append(p / mm if mm != 0 else np.nan)
        rpi_vals.append(p * (1 - fv_raw_vals[i]))

        season_vals.append(month_to_season[m])

    rdf = normalize(np.array(rdf_vals), norm_params["rdf_min"], norm_params["rdf_max"])
    rpi = normalize(np.array(rpi_vals), norm_params["rpi_min"], norm_params["rpi_max"])
    season_tag = np.array(season_vals)

    # =========================
    # WQI
    # =========================
    if "wqi" in df.columns:
      wqi = df["wqi"].values / 100.0
      has_wqi = True
    else:
        wqi = np.full(len(df), np.nan)
        has_wqi = False

    # =========================
    # FINAL OUTPUT
    # =========================
    out_df = pd.DataFrame({
        "station": df["station"],
        "clpi": clpi,
        "dpli": dpli,
        "dss": dss,
        "isf": isf,
        "lfsf": lfsf,
        "plaf": plaf,
        "rdf": rdf,
        "ri": ri,
        "tddf": tddf,
        "tsi": tsi,
        "rpi": rpi,
        "sgp": sgp,
        "season_tag": season_tag,
        "wqi": wqi
    })

    out_path = os.path.join(OUTPUT_DIR, file)
    out_df.to_csv(out_path, index=False)
    print(f"Saved: {file}")

print("\n✅ DONE — FULL FEATURE PIPELINE (FINAL CORRECT)")