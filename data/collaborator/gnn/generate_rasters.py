import os
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
# PATHS
# ======================================================
if len(sys.argv) < 2:
    raise ValueError("Missing collaborator id argument. Usage: python generate_rasters.py <collab_id>")

collab_id = sys.argv[1]
BASE_DIR = f"/home/nitin/software/data/collaborator/{collab_id}/gnn"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

csv_path = os.path.join(SCRIPT_DIR, "wqi_predictions_detailed_test_graphsage.csv")
shp_path = os.path.join(PROJECT_ROOT, "data", "admin", "display", "shp", "narmada_buffer_1000m.shp")
output_folder = os.path.join(BASE_DIR, "wqi_rasters")

os.makedirs(output_folder, exist_ok=True)

# ======================================================
# PARAMETERS
# ======================================================
pixel_size = 500      
idw_power = 2
k_neighbors = 8
tile_size = 500

crs_geo = "EPSG:4326"
crs_utm = "EPSG:32643"

month_order = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

# ======================================================
# READ SHAPE
# ======================================================
print("Reading buffer shapefile...")
gdf = gpd.read_file(shp_path).to_crs(crs_utm)
gdf["geometry"] = gdf.buffer(0)

xmin, ymin, xmax, ymax = gdf.total_bounds

# ======================================================
# READ CSV
# ======================================================
print("Reading WQI CSV...")
df = pd.read_csv(csv_path)

df = df[df["Station"].str.contains("_", na=False)]
df[["Lon", "Lat"]] = df["Station"].str.split("_", expand=True).astype(float)

df = df.dropna(subset=["Predicted", "Lon", "Lat", "Year", "Month"])
df = df.drop_duplicates(subset=["Lon", "Lat", "Year", "Month"])

df["Month"] = pd.Categorical(df["Month"], categories=month_order, ordered=True)

# ======================================================
# PROJECT COORDINATES
# ======================================================
transformer = Transformer.from_crs(crs_geo, crs_utm, always_xy=True)
df["X"], df["Y"] = transformer.transform(df["Lon"].values, df["Lat"].values)

# ======================================================
# GRID SETUP
# ======================================================
nx = int((xmax - xmin) / pixel_size) + 1
ny = int((ymax - ymin) / pixel_size) + 1

transform = from_origin(xmin, ymax, pixel_size, pixel_size)

# ======================================================
# GROUP BY YEAR + MONTH
# ======================================================
groups = df.groupby(["Year", "Month"], observed=True)

for (year, month), group in groups:

    print(f"\nProcessing {year} {month}...")

    if pd.isna(month):
        continue

    x = group["X"].values
    y = group["Y"].values
    z = group["Predicted"].values

    if len(x) < 4:
        print("Skipping (too few stations)")
        continue

    tree = cKDTree(np.column_stack((x, y)))

    # ======================================================
    # IDW FUNCTION 
    # ======================================================
    def idw(gx, gy):
        points = np.column_stack((gx.ravel(), gy.ravel()))

        dist, idx = tree.query(points, k=min(k_neighbors, len(x)))

        if len(dist.shape) == 1:
            dist = dist[:, None]
            idx = idx[:, None]

        weights = 1 / (dist**idw_power + 1e-12)

        exact_match = dist[:, 0] == 0

        zi = np.sum(weights * z[idx], axis=1) / np.sum(weights, axis=1)
        zi[exact_match] = z[idx[exact_match, 0]]

        return zi.reshape(gx.shape)

    raw_path = os.path.join(output_folder, f"temp_{year}_{month}.tif")
    final_path = os.path.join(output_folder, f"wqi_{year}_{month}.tif")

    # ======================================================
    # INTERPOLATION
    # ======================================================
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
    # MASK
    # ======================================================
    with rasterio.open(raw_path) as src:
        out_image, out_transform = mask(
            src,
            gdf.geometry,
            crop=True,
            nodata=-9999
        )
        out_meta = src.meta.copy()

    out_meta.update({
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform,
        "nodata": -9999,
        "compress": "lzw"
    })

    # ======================================================
    # SAVE FINAL
    # ======================================================
    with rasterio.open(final_path, "w", **out_meta) as dest:
        dest.write(out_image)

    os.remove(raw_path)

    print(f"Saved: {final_path}")

print("\nAll rasters generated successfully!")