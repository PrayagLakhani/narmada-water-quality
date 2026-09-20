import os
import re
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window
from rasterio.mask import mask
from pyproj import Transformer
from scipy.spatial import cKDTree
 
# ======================================================
# INPUT YEAR
# ======================================================
year_input = int(sys.argv[1])

# ======================================================
# PATHS
# ======================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

station_folder = os.path.join(BASE_DIR, "data","admin","display", "temp")
narmada_geojson = os.path.join(BASE_DIR, "data","admin","display", "geojson", "narmada.geojson")
output_folder = os.path.join(BASE_DIR, "data","admin","display", "temp", "output_temp_rasters")

os.makedirs(output_folder, exist_ok=True)

pixel_size = 30
idw_power = 2
k_neighbors = 8
tile_size = 500

crs_geo = "EPSG:4326"
crs_utm = "EPSG:32643"

months = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

# ======================================================
# READ SHAPE
# ======================================================
print("Reading Narmada boundary...")
narmada_gdf = gpd.read_file(narmada_geojson).to_crs(crs_utm)
narmada_gdf["geometry"] = narmada_gdf.buffer(0)

xmin, ymin, xmax, ymax = narmada_gdf.total_bounds

# ======================================================
# READ CSV DATA
# ======================================================
print("Reading station files...")
records = []

for file in os.listdir(station_folder):

    if file.startswith("~$"):
        continue    
    if not file.endswith(".xlsx"):
     continue

    nums = re.findall(r"[-+]?\d*\.\d+|\d+", file)
    if len(nums) < 2:
        continue

    lon, lat = float(nums[0]), float(nums[1])

    df = pd.read_excel(os.path.join(station_folder, file))
    df["T_mean"] = df[months].mean(axis=1, skipna=True)

    for _, row in df.iterrows():
        records.append({
            "Year": int(row["Year"]),
            "Lon": lon,
            "Lat": lat,
            "Value": float(row["T_mean"])
        })

data = pd.DataFrame(records)

# ======================================================
# FILTER YEAR
# ======================================================
d = data[data["Year"] == year_input]

if d.empty:
    raise ValueError(f"No records for year {year_input}")

# DEBUG CHECK (IMPORTANT)
print(f"Year {year_input} stats → Min: {d['Value'].min()} Max: {d['Value'].max()}")

# ======================================================
# PROJECT
# ======================================================
transformer = Transformer.from_crs(crs_geo, crs_utm, always_xy=True)
d["X"], d["Y"] = transformer.transform(d["Lon"].values, d["Lat"].values)

x = d["X"].values
y = d["Y"].values
z = d["Value"].values

# ======================================================
# IDW
# ======================================================
tree = cKDTree(np.column_stack((x, y)))

def idw(gx, gy):
    dist, idx = tree.query(
        np.column_stack((gx.ravel(), gy.ravel())),
        k=min(k_neighbors, len(x))
    )

    weights = 1 / (dist + 1e-10) ** idw_power
    zi = np.mean(weights * z[idx], axis=1) / np.mean(weights, axis=1)

    return zi.reshape(gx.shape)

# ======================================================
# GRID
# ======================================================
nx = int((xmax - xmin) / pixel_size) + 1
ny = int((ymax - ymin) / pixel_size) + 1

transform = from_origin(xmin, ymax, pixel_size, pixel_size)

raw_path = os.path.join(output_folder, f"temp_{year_input}.tif")
final_path = os.path.join(output_folder, f"temp_{year_input}_30m.tif")

# ======================================================
# INTERPOLATION
# ======================================================
print("Interpolating...")

with rasterio.open(
    raw_path,
    "w",
    driver="GTiff",
    height=ny,
    width=nx,
    count=1,
    dtype="float32",
    crs=crs_utm,
    transform=transform,
    nodata=-9999 
) as dst:

    for row in range(0, ny, tile_size):
        for col in range(0, nx, tile_size):

            h = min(tile_size, ny - row)
            w = min(tile_size, nx - col)

            xs = xmin + col * pixel_size
            ys = ymax - row * pixel_size

            gx, gy = np.meshgrid(
                xs + np.arange(w) * pixel_size,
                ys - np.arange(h) * pixel_size
            )

            grid = idw(gx, gy)

            dst.write(grid.astype("float32"), 1,
                      window=Window(col, row, w, h))

print("Interpolation done")

# ======================================================
# MASK (SAFE VERSION)
# ======================================================
print("Applying mask...")

with rasterio.open(raw_path) as src:
    out_image, out_transform = mask(
        src,
        narmada_gdf.geometry,
        crop=True,
        nodata=-9999   
    )

    out_meta = src.meta.copy()

# ======================================================
# UPDATE META
# ======================================================
out_meta.update({
    "height": out_image.shape[1],
    "width": out_image.shape[2],
    "transform": out_transform,
    "nodata": -9999,
    "compress": "lzw"
})

# ======================================================
# SAVE
# ======================================================
with rasterio.open(final_path, "w", **out_meta) as dest:
    dest.write(out_image)

os.remove(raw_path)

print(f"Final raster saved: {final_path}")