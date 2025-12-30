import os
import shutil
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


def makeFolder(basePath, year, title):
    """
        Creates a nested folder structure within the specified environment.
        basePath: Path object
        year: str
        title: str
    """
    newPath = basePath / year / title
    newPath.mkdir(parents=True, exist_ok=True)
    return newPath

def moveFolder(image, source, dest):
    """
        Moves the image from source to dest
        image: str
        source: Path object
        dest: str
    """
    sourcePath = source / image
    destinationPath = Path(dest) / image
    
    # Move the file from the source to dest as defined above
    if not source.exists():
        raise FileNotFoundError(f"Source file '{image}' not found in '{source}'")
    shutil.move(str(sourcePath), str(destinationPath))

    return



def get_exif_data(image_path):
    """Reads all EXIF data from an image file."""
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
    except Exception:
        # Handle cases where the file isn't an image, is corrupt, or has no EXIF
        return None

    if not exif_data:
        return None

    # Decode the tags from numbers to readable names
    decoded_data = {}
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)
        decoded_data[tag] = value
    
    return decoded_data


def convert_dms_to_degrees(dms):
    """
    Converts the Degrees, Minutes, Seconds format to decimal degrees.
    Handles IFDRational objects directly from newer Pillow versions.
    dms is a tuple of (degrees, minutes, seconds)
    """
    try:
        # Check if the values are tuples (numerator, denominator) for backward compatibility
        d = dms[0][0] / dms[0][1]
        m = dms[1][0] / dms[1][1]
        s = dms[2][0] / dms[2][1]
    except TypeError:
        # If the values are IFDRational objects, access them directly
        # The IFDRational object often acts as a rational number (numerator/denominator)
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])
    
    return d + (m / 60.0) + (s / 3600.0)


def get_lat_lon(exif_data):
    """Extracts latitude and longitude from the EXIF GPS data."""
    gps_info = {}
    if 'GPSInfo' in exif_data:
        for tag_id, value in exif_data['GPSInfo'].items():
            # Decode the GPS tags
            tag = GPSTAGS.get(tag_id, tag_id)
            gps_info[tag] = value

        lat = None
        lon = None
        if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
            lat = convert_dms_to_degrees(gps_info['GPSLatitude'])
            if gps_info['GPSLatitudeRef'] != 'N':
                lat = -lat
        if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
            lon = convert_dms_to_degrees(gps_info['GPSLongitude'])
            if gps_info['GPSLongitudeRef'] != 'E':
                lon = -lon
        return lat, lon
    return None, None


# --- Configuration ---
# Initialize Geolocator
geolocator = Nominatim(user_agent="photo_sorter_app")
# Cache to store looked-up coordinates so we don't spam the API
# Format: {(rounded_lat, rounded_lon): "CityName"}
location_cache = dict()

def get_location_name(lat, lon):
    """
    Returns a city/town name for the given coordinates.
    lat, lon: int, int
    """
    # Round coordinates to 1 decimal places, method to cluster images
    lat_key = round(lat, 1)
    lon_key = round(lon, 1)
    
    if (lat_key, lon_key) in location_cache:
        return location_cache[(lat_key, lon_key)]

    # If not in cache, ask the API
    try:
        location = geolocator.reverse(f"{lat}, {lon}", timeout=5)
        if location:
            address = location.raw.get('address', {})
            # Try to find the most relevant area name
            area = (address.get('city') or 
                    address.get('town') or 
                    address.get('village') or 
                    address.get('suburb') or 
                    address.get('county') or 
                    "Unknown_Location")
            # Save to cache
            location_cache[(lat_key, lon_key)] = area
            return area
    except Exception as e:
        print(f"    ! Geocoding warning: {e}")
    
    return "Unknown_Location"


def categImg(folder_path, base_output):
    """
    Scans folder from folder_path and organizes photos into Output/Year/Location in base_output.
    folder_path: str
    base_output: str
    """
    # Convert strings to Path objects
    source_dir = Path(folder_path)
    base_output = Path(base_output)
    supported_extensions = ('.jpg', '.jpeg', '.png')

    print(f"--- Organizing photos from: '{source_dir}' ---")

    if not source_dir.exists():
        print(f"Error: Source folder '{source_dir}' not found.")
        return

    for file_path in source_dir.iterdir():
        # Skip if directory or non-image
        if file_path.is_dir() or not file_path.suffix.lower().endswith(supported_extensions):
            continue

        print(f"Processing: {file_path.name}")
        
        # Get Metadata
        exif_data = get_exif_data(str(file_path))
        
        # Default Year if metadata fails
        year = "0000_NoDate"
        
        if exif_data:
            # Extract MetaData
            date_time = exif_data.get('DateTimeOriginal') or exif_data.get('DateTime')
            if date_time:
                year = date_time[:4] # Get first 4 chars (YYYY)
            # Extract Location
            lat, lon = get_lat_lon(exif_data)
            
            # Grouping into folders based on location
            if lat and lon:
                imageID = str(file_path)[5:]
                location_name = get_location_name(lat, lon)
                testPath = base_output / year / location_name
                if testPath.exists():
                    print(f"  -> Detected: {year} / {location_name}")
                    moveFolder(imageID, source_dir, testPath)
                else:
                    target_folder = makeFolder(base_output, year, location_name)
                    moveFolder(imageID, source_dir, target_folder)
            else:
                # No Location -> Leave in Year folder
                print(f"  -> No GPS. Not performing anything")
                # target_folder = makeFolder(base_output, year, None)
        else:
            # No EXIF data at all
            print(f"  -> No EXIF detected for {file_path}")
            # target_folder = makeFolder(base_output, year, None)

categImg('Temp', 'Photos')