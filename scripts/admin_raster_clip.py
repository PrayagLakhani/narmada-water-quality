import os
import subprocess
import tempfile


def admin_clip_precipitation_raster():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    input_raster = os.path.join(BASE_DIR, "data","admin","display", "raster", "2011_2023_Precipitation.tif")
    basin_geojson = os.path.join(BASE_DIR, "data", "admin","display", "geojson", "narmada.geojson")
    output_raster = os.path.join(BASE_DIR, "data", "admin","display", "raster", "precip_clipped.tif")

    valid_geojson = os.path.join(tempfile.gettempdir(), "narmada_valid.geojson")

    subprocess.run(
        ["ogr2ogr", "-makevalid", valid_geojson, basin_geojson],
        check=True
    )

    subprocess.run(
        [
            "gdalwarp",
            "-cutline", valid_geojson,
            "-crop_to_cutline",
            "-multi",
            "-of", "GTiff",
            "-co", "TILED=YES",
            "-co", "COMPRESS=DEFLATE",
            "-co", "BIGTIFF=YES",
            "-overwrite",
            input_raster,
            output_raster
        ],
        check=True
    )

    print("Precipitation raster clipped successfully")


def admin_clip_temperature_raster():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    input_raster = os.path.join(BASE_DIR, "data","admin","display", "raster", "2011_2023_Mean_Temperature.tif")
    basin_geojson = os.path.join(BASE_DIR, "data","admin","display", "geojson", "narmada.geojson")
    output_raster = os.path.join(BASE_DIR, "data","admin","display", "raster", "temp_clipped.tif")

    valid_geojson = os.path.join(tempfile.gettempdir(), "narmada_valid.geojson")

    subprocess.run(
        ["ogr2ogr", "-makevalid", valid_geojson, basin_geojson],
        check=True
    )

    subprocess.run(
        [
            "gdalwarp",
            "-cutline", valid_geojson,
            "-crop_to_cutline",
            "-multi",
            "-of", "GTiff",
            "-co", "TILED=YES",
            "-co", "COMPRESS=DEFLATE",
            "-co", "BIGTIFF=YES",
            "-overwrite",
            input_raster,
            output_raster
        ],
        check=True
    )

    print("Mean temperature raster clipped successfully")



def collaborator_clip_precipitation_raster(collab_id):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    input_raster = os.path.join(BASE_DIR, "data","collaborator",collab_id,"display", "raster", "precip_raster.tif")
    basin_geojson = os.path.join(BASE_DIR, "data", "collaborator",collab_id,"display", "geojson", "narmada.geojson")
    output_raster = os.path.join(BASE_DIR, "data", "collaborator",collab_id,"display", "raster", "precip_clipped.tif")

    valid_geojson = os.path.join(tempfile.gettempdir(), "narmada_valid.geojson")

    subprocess.run(
        ["ogr2ogr", "-makevalid", valid_geojson, basin_geojson],
        check=True
    )

    subprocess.run(
        [
            "gdalwarp",
            "-cutline", valid_geojson,
            "-crop_to_cutline",
            "-multi",
            "-of", "GTiff",
            "-co", "TILED=YES",
            "-co", "COMPRESS=DEFLATE",
            "-co", "BIGTIFF=YES",
            "-overwrite",
            input_raster,
            output_raster
        ],
        check=True
    )

    print("Precipitation raster clipped successfully")


def collaborator_clip_temperature_raster(collab_id):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    input_raster = os.path.join(BASE_DIR, "data","collaborator",collab_id,"display", "raster", "temp_raster.tif")
    basin_geojson = os.path.join(BASE_DIR, "data","collaborator",collab_id,"display", "geojson", "narmada.geojson")
    output_raster = os.path.join(BASE_DIR, "data","collaborator",collab_id,"display", "raster", "temp_clipped.tif")

    valid_geojson = os.path.join(tempfile.gettempdir(), "narmada_valid.geojson")

    subprocess.run(
        ["ogr2ogr", "-makevalid", valid_geojson, basin_geojson],
        check=True
    )

    subprocess.run(
        [
            "gdalwarp",
            "-cutline", valid_geojson,
            "-crop_to_cutline",
            "-multi",
            "-of", "GTiff",
            "-co", "TILED=YES",
            "-co", "COMPRESS=DEFLATE",
            "-co", "BIGTIFF=YES",
            "-overwrite",
            input_raster,
            output_raster
        ],
        check=True
    )

    print("Mean temperature raster clipped successfully")