import os
import sys
import pandas as pd
import numpy as np
import json
import rasterio

import geopandas as gpd
from rasterio.mask import mask
# -----------------------------
# BASE DIRECTORY
# -----------------------------
if len(sys.argv) < 2:
    raise ValueError("Missing collaborator id argument. Usage: python app.py <collab_id>")

collab_id = sys.argv[1]
BASE_DIR = f"/home/nitin/software/data/collaborator/{collab_id}/gnn"


##------------------from streamflow---------------------------------------------

streamflow_dir = os.path.join(BASE_DIR,"training_input","streamflow")

dci_dir = os.path.join(BASE_DIR,"training_gnn", "dci_output")
lfsf_dir = os.path.join(BASE_DIR,"training_gnn", "lfsf_output")
plaf_dir = os.path.join(BASE_DIR,"training_gnn", "plaf_output")

os.makedirs(dci_dir, exist_ok=True)
os.makedirs(lfsf_dir, exist_ok=True)
os.makedirs(plaf_dir, exist_ok=True)

# -----------------------------
# STEP 1: COLLECT ALL VALUES
# -----------------------------
all_values = []

files = [f for f in os.listdir(streamflow_dir) if f.endswith(".csv")]

for file in files:
    df = pd.read_csv(os.path.join(streamflow_dir, file))
    
    values = df.iloc[:, 1:].values.flatten()
    values = values[~np.isnan(values)]
    
    all_values.extend(values)

all_values = np.array(all_values)

Q_mean_basin = np.mean(all_values)
Q10 = np.percentile(all_values, 10)

print("Q_mean_basin:", Q_mean_basin)
print("Q10:", Q10)

# -----------------------------
# STEP 2: COMPUTE PARAMETERS
# -----------------------------
dci_data = {}
lfsf_data = {}
plaf_data = {}

for file in files:
    path = os.path.join(streamflow_dir, file)
    df = pd.read_csv(path)

    values = df.iloc[:, 1:].values.astype(float)

    # ---- DCI ----
    dci = values / Q_mean_basin

    # ---- LFSF ----
    lfsf = np.where(np.isnan(values), np.nan,
                    np.where(values < Q10, 1, 0))

    # ---- PLAF ----
    with np.errstate(divide='ignore', invalid='ignore'):
        plaf = 1 / dci
        plaf[np.isinf(plaf)] = np.nan

    dci_data[file] = (df.copy(), dci)
    lfsf_data[file] = (df.copy(), lfsf)
    plaf_data[file] = (df.copy(), plaf)

# -----------------------------
# STEP 3: NORMALIZATION FUNCTION
# -----------------------------
def normalize_all(data_dict):
    all_vals = []

    for _, (_, vals) in data_dict.items():
        flat = vals.flatten()
        flat = flat[~np.isnan(flat)]
        all_vals.extend(flat)

    all_vals = np.array(all_vals)

    if all_vals.size == 0:
        norm_dict = {}
        for file, (df, vals) in data_dict.items():
            norm_df = df.copy()
            norm_vals = np.where(np.isnan(vals), np.nan, 0.0)
            norm_df.iloc[:, 1:] = norm_vals
            norm_dict[file] = norm_df
        return norm_dict, 0.0, 0.0

    vmin = np.min(all_vals)
    vmax = np.max(all_vals)

    if vmax == vmin:
        norm_dict = {}
        for file, (df, vals) in data_dict.items():
            norm_df = df.copy()
            norm_vals = np.where(np.isnan(vals), np.nan, 0.0)
            norm_df.iloc[:, 1:] = norm_vals
            norm_dict[file] = norm_df
        return norm_dict, float(vmin), float(vmax)

    norm_dict = {}

    for file, (df, vals) in data_dict.items():
        norm_vals = (vals - vmin) / (vmax - vmin)
        norm_df = df.copy()
        norm_df.iloc[:, 1:] = norm_vals
        norm_dict[file] = norm_df

    return norm_dict, vmin, vmax

# -----------------------------
# STEP 4: NORMALIZE
# -----------------------------
dci_norm, dci_min, dci_max = normalize_all(dci_data)
plaf_norm, plaf_min, plaf_max = normalize_all(plaf_data)

# LFSF (no normalization)
lfsf_final = {}

for file, (df, vals) in lfsf_data.items():
    out_df = df.copy()
    out_df.iloc[:, 1:] = vals
    lfsf_final[file] = out_df

# -----------------------------
# STEP 5: SAVE OUTPUTS
# -----------------------------


for file in files:
    (dci_norm[file]).to_csv(os.path.join(dci_dir, file), index=False)
    (lfsf_final[file]).to_csv(os.path.join(lfsf_dir, file), index=False)
    (plaf_norm[file]).to_csv(os.path.join(plaf_dir, file), index=False)

# -----------------------------
# STEP 6: SAVE NORMALIZATION PARAMS
# -----------------------------
norm_params = {
    "Q_mean_basin": float(Q_mean_basin),
    "Q10": float(Q10),
    "dci_min": float(dci_min),
    "dci_max": float(dci_max),
    "plaf_min": float(plaf_min),
    "plaf_max": float(plaf_max)
}

with open(os.path.join(BASE_DIR,"norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)
    
print("✅ DCI, LFSF, PLAF computed and saved successfully.")
print("✅ Normalization parameters saved to norm_params.json")









# =============================================================================
# ----------------------------- WQI NORMALIZATION ------------------------------
# =============================================================================

wqi_input_dir = os.path.join(BASE_DIR,"training_input","wqi")
wqi_output_dir = os.path.join(BASE_DIR, "training_gnn","wqi_normalized")


os.makedirs(wqi_output_dir, exist_ok=True)

# -----------------------------
# STEP 1: COLLECT ALL WQI VALUES
# -----------------------------
all_wqi_values = []

wqi_files = [f for f in os.listdir(wqi_input_dir) if f.endswith(".csv")]

for file in wqi_files:
    df = pd.read_csv(os.path.join(wqi_input_dir, file))

    values = df.iloc[:, 1:].values.flatten()
    values = values[~np.isnan(values)]

    all_wqi_values.extend(values)

all_wqi_values = np.array(all_wqi_values)

wqi_min = np.min(all_wqi_values)
wqi_max = np.max(all_wqi_values)

print("WQI Min:", wqi_min)
print("WQI Max:", wqi_max)

# -----------------------------
# STEP 2: NORMALIZE WQI
# -----------------------------
wqi_norm_data = {}

for file in wqi_files:
    path = os.path.join(wqi_input_dir, file)
    df = pd.read_csv(path)

    ##values = df.iloc[:, 1:].values.astype(float)
    
    values = df.iloc[:, 1:].values.astype(float)

    # 🔥 FIX: remove extreme spikes
    #values = np.clip(values, None, 100)

    # normalize safely
    #norm_vals = (values - wqi_min) / (wqi_max - wqi_min + 1e-8)
    norm_vals = values / 100.0
    #norm_vals= np.clip(norm_vals, 0.05, 0.95)
    
    out_df = df.copy()
    out_df.iloc[:, 1:] = norm_vals

    wqi_norm_data[file] = out_df

# -----------------------------
# STEP 3: SAVE NORMALIZED WQI
# -----------------------------
for file in wqi_files:
    (wqi_norm_data[file]).to_csv(os.path.join(wqi_output_dir, file), index=False)


# -----------------------------
# STEP 4: UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "wqi_min": float(wqi_min),
    "wqi_max": float(wqi_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)
with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ WQI normalized and saved successfully.")

















##-------------------from water level-----------------------
# -----------------------------
# WATER LEVEL → RECESSION INDEX (RI)
# -----------------------------
waterlevel_dir = os.path.join(BASE_DIR,"training_input", "waterlevel")
ri_dir = os.path.join(BASE_DIR,"training_gnn","ri_output")

os.makedirs(ri_dir, exist_ok=True)

# -----------------------------
# STEP 1: COLLECT ALL WATER LEVEL VALUES
# -----------------------------
all_h_values = []

wl_files = [f for f in os.listdir(waterlevel_dir) if f.endswith(".csv")]

for file in wl_files:
    df = pd.read_csv(os.path.join(waterlevel_dir, file))
    
    values = df.iloc[:, 1:].values.flatten()
    values = values[~np.isnan(values)]
    
    all_h_values.extend(values)

all_h_values = np.array(all_h_values)

H_mean = np.mean(all_h_values)

print("H_mean (water level):", H_mean)

# -----------------------------
# STEP 2: COMPUTE RI
# -----------------------------
ri_data = {}

for file in wl_files:
    path = os.path.join(waterlevel_dir, file)
    df = pd.read_csv(path)

    values = df.iloc[:, 1:].values.astype(float)

    # ---- RI ----
    ri = (H_mean - values) / H_mean

    ri_data[file] = (df.copy(), ri)

# -----------------------------
# STEP 3: NORMALIZE RI
# -----------------------------
ri_norm, ri_min, ri_max = normalize_all(ri_data)

# -----------------------------
# STEP 4: SAVE RI FILES
# -----------------------------
for file in wl_files:
    (ri_norm[file]).to_csv(os.path.join(ri_dir, file), index=False)
    

# -----------------------------
# STEP 5: UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "H_mean": float(H_mean),
    "ri_min": float(ri_min),
    "ri_max": float(ri_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ RI computed and saved successfully.")

























##-------------------from temperature-----------------------

# -----------------------------
# DIRECTORIES
# -----------------------------
maxt_dir = os.path.join(BASE_DIR,"training_input", "maxt")
mint_dir = os.path.join(BASE_DIR,"training_input", "mint")

tsi_dir = os.path.join(BASE_DIR,"training_gnn", "tsi_output")
tddf_dir = os.path.join(BASE_DIR,"training_gnn","tddf_output")
dss_dir = os.path.join(BASE_DIR,"training_gnn","dss_output")


os.makedirs(tsi_dir, exist_ok=True)
os.makedirs(tddf_dir, exist_ok=True)
os.makedirs(dss_dir, exist_ok=True)

# -----------------------------
# CONSTANT
# -----------------------------
T_threshold = 30.0

# -----------------------------
# READ FILES
# -----------------------------
maxt_files = [f for f in os.listdir(maxt_dir) if f.endswith(".csv")]

# -----------------------------
# COMPUTE FEATURES
# -----------------------------
tsi_data = {}
tddf_data = {}
dss_data = {}

for file in maxt_files:
    max_path = os.path.join(maxt_dir, file)
    min_path = os.path.join(mint_dir, file)

    if not os.path.exists(min_path):
        continue

    df_max = pd.read_csv(max_path)
    df_min = pd.read_csv(min_path)

    Tmax = df_max.iloc[:, 1:].values.astype(float)
    Tmin = df_min.iloc[:, 1:].values.astype(float)

    # ---- TSI ----
    tsi = (Tmax - T_threshold) / T_threshold

    # ---- TDDF ----
    with np.errstate(divide='ignore', invalid='ignore'):
        DO_sat = 468 / (31.6 + Tmax)

    DO_sat_max = 468 / (31.6 + 0)
    tddf = DO_sat / DO_sat_max

    # ---- DSS ----
    dss = Tmax - Tmin

    tsi_data[file] = (df_max.copy(), tsi)
    tddf_data[file] = (df_max.copy(), tddf)
    dss_data[file] = (df_max.copy(), dss)

# -----------------------------
# NORMALIZE
# -----------------------------
tsi_norm, tsi_min, tsi_max = normalize_all(tsi_data)
tddf_norm, tddf_min, tddf_max = normalize_all(tddf_data)
dss_norm, dss_min, dss_max = normalize_all(dss_data)

# -----------------------------
# SAVE OUTPUTS
# -----------------------------

for file in tsi_data.keys():
    (tsi_norm[file]).to_csv(os.path.join(tsi_dir, file), index=False)
    (tddf_norm[file]).to_csv(os.path.join(tddf_dir, file), index=False)
    (dss_norm[file]).to_csv(os.path.join(dss_dir, file), index=False)
    
    
# -----------------------------
# UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "T_threshold": T_threshold,
    "tsi_min": float(tsi_min),
    "tsi_max": float(tsi_max),
    "tddf_min": float(tddf_min),
    "tddf_max": float(tddf_max),
    "dss_min": float(dss_min),
    "dss_max": float(dss_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)
    
with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ Temperature features computed and saved successfully.")






























# -----------------------------
# APC MAPPING (LULC → POLLUTION SCORE)
# -----------------------------
apc_mapping = {
    14: 0.9, 15: 0.9,   # built-up
    13: 0.7,            # peri-urban
    11: 0.6,            # irrigated agri
    12: 0.4,            # rainfed agri
    16: 0.2,            # barren
    0: 0.0, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05, 6: 0.05, 7: 0.05,
    8: 0.05, 9: 0.05, 10: 0.05,  # vegetation
    17: 0.0             # water
}

built_classes = [14, 15]  # for ISF
vegetation_classes = [0,1,2,3,4,5,6,7,8,9,10]  # for FV

# -----------------------------
# FUNCTION: COMPUTE CLPI, ISF, FV FOR A CATCHMENT
# -----------------------------
def compute_lulc_metrics_catchment(raster_path, catchment_geom):
    if not os.path.exists(raster_path):
        return np.nan, np.nan, np.nan

    with rasterio.open(raster_path) as src:
        try:
            out_image, _ = mask(src, [catchment_geom], crop=True)
            band = out_image[0]
            nodata = src.nodata

            # remove nodata
            if nodata is not None:
                band = band[band != nodata]

            band = band[~np.isnan(band)]
            if len(band) == 0:
                return np.nan, np.nan, np.nan

            # CLPI
            apc_vals = np.array([apc_mapping.get(int(round(v)), 0.3) for v in band])
            clpi = np.mean(apc_vals)

            # ISF
            isf = np.sum(np.isin(np.round(band).astype(int), built_classes)) / len(band)

            # Fraction Vegetation
            fv = np.sum(np.isin(np.round(band).astype(int), vegetation_classes)) / len(band)

        except Exception as e:
            print(f"Error computing metrics: {e}")
            return np.nan, np.nan, np.nan

    return clpi, isf, fv

# -----------------------------
# MAIN PROCESSING
# -----------------------------
lulc_dir = os.path.join(BASE_DIR,"training_input", "lulc")
clpi_dir = os.path.join(BASE_DIR,"training_gnn", "clpi_output")
isf_dir = os.path.join(BASE_DIR,"training_gnn", "isf_output")
fv_dir   = os.path.join(BASE_DIR,"training_gnn","fv_output")

os.makedirs(clpi_dir, exist_ok=True)
os.makedirs(isf_dir, exist_ok=True)
os.makedirs(fv_dir, exist_ok=True)

ref_dir = streamflow_dir
lulc_files = [f for f in os.listdir(ref_dir) if f.endswith(".csv")]

clpi_data = {}
isf_data = {}
fv_data   = {}

# -----------------------------
# READ ALL STATIONS
# -----------------------------
stations = []
for file in lulc_files:
    path = os.path.join(ref_dir, file)
    df = pd.read_csv(path)
    name = file.replace(".csv", "")
    lon, lat = map(float, name.split("_"))
    years = df.iloc[:, 0].values
    n_rows = len(years)
    n_months = df.shape[1] - 1

    catchment_geom = {
        "type": "Polygon",
        "coordinates": [[
            [lon-0.01, lat-0.01],
            [lon+0.01, lat-0.01],
            [lon+0.01, lat+0.01],
            [lon-0.01, lat+0.01],
            [lon-0.01, lat-0.01]
        ]]
    }

    stations.append({
        "file": file,
        "df": df,
        "lon": lon,
        "lat": lat,
        "years": years,
        "n_rows": n_rows,
        "n_months": n_months,
        "clpi_vals": np.zeros((n_rows, n_months)),
        "isf_vals": np.zeros((n_rows, n_months)),
        "fv_vals":   np.zeros((n_rows, n_months)),
        "catchment_geom": catchment_geom
    })

# -----------------------------
# PROCESS YEAR-WISE
# -----------------------------
all_years = sorted(list(set(int(y) for s in stations for y in s["years"])))

for year in all_years:
    raster_path = os.path.join(lulc_dir, f"{year}.tif")
    if not os.path.exists(raster_path):
        continue

    for s in stations:
        for i, y in enumerate(s["years"]):
            if int(y) != year:
                continue

            clpi, isf, fv = compute_lulc_metrics_catchment(raster_path, s["catchment_geom"])

            # fallback values
            if np.isnan(clpi):
                clpi = 0.3
            if np.isnan(isf):
                isf = 0.1
            if np.isnan(fv):
                fv = 0.5  # arbitrary default if vegetation fraction unknown

            # fill all months
            s["clpi_vals"][i, :] = clpi
            s["isf_vals"][i, :] = isf
            s["fv_vals"][i, :]   = fv

# -----------------------------
# STORE RESULTS
# -----------------------------
for s in stations:
    clpi_data[s["file"]] = (s["df"].copy(), s["clpi_vals"])
    isf_data[s["file"]] = (s["df"].copy(), s["isf_vals"])
    fv_data[s["file"]]   = (s["df"].copy(), s["fv_vals"])


# -----------------------------
# NORMALIZE
# -----------------------------
clpi_norm, clpi_min, clpi_max = normalize_all(clpi_data)
isf_norm, isf_min, isf_max = normalize_all(isf_data)
fv_norm, fv_min, fv_max       = normalize_all(fv_data)

for file in lulc_files:
    (clpi_norm[file]).to_csv(os.path.join(clpi_dir, file), index=False)
    (isf_norm[file]).to_csv(os.path.join(isf_dir, file), index=False)
    (fv_norm[file]).to_csv(os.path.join(fv_dir, file), index=False)


# -----------------------------
# UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "clpi_min": float(clpi_min),
    "clpi_max": float(clpi_max),
    "isf_min": float(isf_min),
    "isf_max": float(isf_max),
    "fv_min":   float(fv_min),
    "fv_max":   float(fv_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ LULC features (CLPI, ISF, FV) computed successfully using catchments.")















######pop density
##-------------------from POPULATION (OPTIMIZED)-----------------------

pop_dir = os.path.join(BASE_DIR,"training_input", "pop")

dpli_dir = os.path.join(BASE_DIR,"training_gnn", "dpli_output")
sgp_dir = os.path.join(BASE_DIR, "training_gnn","sgp_output")

os.makedirs(dpli_dir, exist_ok=True)
os.makedirs(sgp_dir, exist_ok=True)

# Reference station files
ref_dir = streamflow_dir
pop_files = [f for f in os.listdir(ref_dir) if f.endswith(".csv")]

dpli_data = {}
sgp_data = {}

# Constants
L_percapita = 135.0
T_coverage = 0.3

# -----------------------------
# STEP 1: READ ALL STATIONS
# -----------------------------
stations = []

for file in pop_files:
    path = os.path.join(ref_dir, file)
    df = pd.read_csv(path)

    name = file.replace(".csv", "")
    lon, lat = map(float, name.split("_"))

    years = df.iloc[:, 0].values
    n_rows = len(years)
    n_months = df.shape[1] - 1

    stations.append({
        "file": file,
        "df": df,
        "lon": lon,
        "lat": lat,
        "years": years,
        "n_rows": n_rows,
        "n_months": n_months,
        "dpli_vals": np.zeros((n_rows, n_months)),
        "sgp_vals": np.zeros((n_rows, n_months))
    })

# -----------------------------
# STEP 2: GET ALL YEARS
# -----------------------------
all_years = sorted(list(set(
    int(y) for s in stations for y in s["years"]
)))

# -----------------------------
# STEP 3: COMPUTE BASIN MEAN (ρ_mean)
# -----------------------------
all_pop_values = []

for year in all_years:
    raster_path = os.path.join(pop_dir, f"{year}.tif")

    if not os.path.exists(raster_path):
        continue

    with rasterio.open(raster_path) as src:
        band = src.read(1)
        nodata = src.nodata

        valid_pixels = band.flatten()

        if nodata is not None:
            valid_pixels = valid_pixels[valid_pixels != nodata]

        valid_pixels = valid_pixels[~np.isnan(valid_pixels)]
        valid_pixels = valid_pixels[valid_pixels > 0]

        all_pop_values.extend(valid_pixels)

rho_mean_basin = np.mean(all_pop_values)
print("ρ_mean_basin:", rho_mean_basin)

# -----------------------------
# STEP 4: PROCESS YEAR-WISE (OPTIMIZED)
# -----------------------------
for year in all_years:
    raster_path = os.path.join(pop_dir, f"{year}.tif")

    if not os.path.exists(raster_path):
        continue

    with rasterio.open(raster_path) as src:
        band = src.read(1)
        nodata = src.nodata

        for s in stations:
            for i, y in enumerate(s["years"]):
                if int(y) != year:
                    continue

                try:
                    row, col = src.index(s["lon"], s["lat"])
                    rho = band[row, col]

                except:
                    rho = np.nan

                # clean value
                if nodata is not None and rho == nodata:
                    rho = np.nan

                if np.isnan(rho) or rho <= 0:
                    rho = rho_mean_basin

                # -----------------------------
                # DPLI
                # -----------------------------
                dpli = rho / rho_mean_basin if rho_mean_basin != 0 else 0

                # -----------------------------
                # SGP
                # -----------------------------
                sgp = rho * L_percapita * (1 - T_coverage)

                # fill all months
                s["dpli_vals"][i, :] = dpli
                s["sgp_vals"][i, :] = sgp

# -----------------------------
# STEP 5: STORE RESULTS
# -----------------------------
for s in stations:
    dpli_data[s["file"]] = (s["df"].copy(), s["dpli_vals"])
    sgp_data[s["file"]] = (s["df"].copy(), s["sgp_vals"])

# -----------------------------
# NORMALIZE (SAFE)
# -----------------------------
def safe_normalize(data_dict):
    all_vals = np.concatenate([vals.flatten() for _, vals in data_dict.values()])
    vmin = np.nanmin(all_vals)
    vmax = np.nanmax(all_vals)

    norm_dict = {}

    for file, (df, vals) in data_dict.items():
        if vmax == vmin:
            norm_vals = np.zeros_like(vals)
        else:
            norm_vals = (vals - vmin) / (vmax - vmin)

        df_out = df.copy()
        df_out.iloc[:, 1:] = norm_vals
        norm_dict[file] = df_out

    return norm_dict, vmin, vmax

dpli_norm, dpli_min, dpli_max = safe_normalize(dpli_data)
sgp_norm, sgp_min, sgp_max = safe_normalize(sgp_data)

# -----------------------------
# SAVE OUTPUTS
# -----------------------------
for file in pop_files:
   (dpli_norm[file]).to_csv(os.path.join(dpli_dir, file), index=False)
   (sgp_norm[file]).to_csv(os.path.join(sgp_dir, file), index=False)

# -----------------------------
# UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "dpli_min": float(dpli_min),
    "dpli_max": float(dpli_max),
    "sgp_min": float(sgp_min),
    "sgp_max": float(sgp_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ Population features (DPLI, SGP) computed and saved successfully (FAST VERSION).")















precip_dir = os.path.join(BASE_DIR,"training_input", "precip")
fv_dir = os.path.join(BASE_DIR,"training_gnn", "fv_output")  # vegetated fraction rasters

rdf_dir = os.path.join(BASE_DIR,"training_gnn", "rdf_output")
rpi_dir = os.path.join(BASE_DIR, "training_gnn","rpi_output")
season_dir = os.path.join(BASE_DIR,"training_gnn", "season_tag_output")


os.makedirs(rdf_dir, exist_ok=True)
os.makedirs(rpi_dir, exist_ok=True)
os.makedirs(season_dir, exist_ok=True)

# -----------------------------
# SEASONAL TAGS
# -----------------------------
month_to_season = {
    0: "Winter", 1: "Winter",
    2: "Pre-monsoon", 3: "Pre-monsoon", 4: "Pre-monsoon",
    5: "Monsoon", 6: "Monsoon", 7: "Monsoon", 8: "Monsoon",
    9: "Post-monsoon", 10: "Post-monsoon",
    11: "Winter"
}

# -----------------------------
# READ FILES
# -----------------------------
precip_files = [f for f in os.listdir(precip_dir) if f.endswith(".csv")]

rdf_data = {}
rpi_data = {}
season_data = {}
all_precip_values = []

# -----------------------------
# STEP 1: COLLECT ALL PRECIP VALUES
# -----------------------------
for file in precip_files:
    df = pd.read_csv(os.path.join(precip_dir, file))
    values = df.iloc[:, 1:].values.flatten()
    values = values[~np.isnan(values)]
    all_precip_values.extend(values)

all_precip_values = np.array(all_precip_values)

# Compute long-term mean per month
month_means = {}
for m in range(12):
    month_values = all_precip_values[m::12]  # approximate monthly mean across all years
    month_values = month_values[~np.isnan(month_values)]
    month_means[m] = np.mean(month_values)

print("Monthly mean precipitation:", month_means)

# -----------------------------
# STEP 2: COMPUTE RDF, RPI, SEASON
# -----------------------------
for file in precip_files:
    path = os.path.join(precip_dir, file)
    df = pd.read_csv(path)

    P = df.iloc[:, 1:].values.astype(float)
    years = df.iloc[:, 0].values

    # Vegetated fraction
    fv_file = os.path.join(fv_dir, file)
    if os.path.exists(fv_file):
        fv_df = pd.read_csv(fv_file)
        f_veg = fv_df.iloc[:, 1:].values.astype(float)
    else:
        f_veg = np.zeros_like(P)

    rdf = np.zeros_like(P)
    rpi = np.zeros_like(P)
    season_tag = np.empty(P.shape, dtype=object)

    for i in range(P.shape[0]):
        for j in range(P.shape[1]):
            if np.isnan(P[i, j]):
                rdf[i, j] = np.nan
                rpi[i, j] = np.nan
                season_tag[i, j] = None
                continue

            rdf[i, j] = P[i, j] / month_means[j]
            rpi[i, j] = P[i, j] * (1 - f_veg[i, j])
            season_tag[i, j] = month_to_season[j]

    rdf_data[file] = (df.copy(), rdf)
    rpi_data[file] = (df.copy(), rpi)

    # Create a **new DataFrame** for season (avoids dtype warning)
    season_df = pd.DataFrame(season_tag, columns=df.columns[1:])
    season_df.insert(0, df.columns[0], df.iloc[:, 0])  # keep year column
    season_data[file] = season_df

# -----------------------------
# STEP 3: NORMALIZE RDF, RPI
# -----------------------------
rdf_norm, rdf_min, rdf_max = normalize_all(rdf_data)
rpi_norm, rpi_min, rpi_max = normalize_all(rpi_data)

# -----------------------------
# STEP 4: SAVE OUTPUTS
# -----------------------------
for file in precip_files:
    (rdf_norm[file]).to_csv(os.path.join(rdf_dir, file), index=False)
    (rpi_norm[file]).to_csv(os.path.join(rpi_dir, file), index=False)
    (season_data[file]).to_csv(os.path.join(season_dir, file), index=False)


# -----------------------------
# STEP 5: UPDATE NORMALIZATION PARAMS
# -----------------------------
norm_params.update({
    "rdf_min": float(rdf_min),
    "rdf_max": float(rdf_max),
    "rpi_min": float(rpi_min),
    "rpi_max": float(rpi_max)
})

with open(os.path.join(BASE_DIR, "norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

with open(os.path.join(BASE_DIR, "training_gnn","norm_params.json"), "w") as f:
    json.dump(norm_params, f, indent=4)

print("✅ Precipitation features (RDF, RPI, Season) computed and saved successfully.")