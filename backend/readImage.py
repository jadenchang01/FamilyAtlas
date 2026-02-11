from pathlib import Path
import os
import shutil
import mimetypes
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geopy.distance import geodesic
import cv2
import numpy as np


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


def extractImageID(stringFilePath):
    slash_index = stringFilePath.rfind('/')
    if slash_index != -1:
        return stringFilePath[slash_index+1:]
    return stringFilePath


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
location_cache = dict()

def get_location_name(lat, lon):
    """
    Returns a city/town name for Korea, or Country name for elsewhere.
    lat, lon: int, int
    """
    
    # Check if Home (within 1km radius)
    # Provided: 37.519355555555556, 127.01368611111111
    HOME_COORDS = (37.519355555555556, 127.01368611111111)
    try:
        if geodesic(HOME_COORDS, (lat, lon)).km <= 1.0:
            return "Home"
    except Exception:
        pass

    # Round coordinates to 1 decimal places to cluster images
    lat_key = round(lat, 1)
    lon_key = round(lon, 1)
    
    if (lat_key, lon_key) in location_cache:
        return location_cache[(lat_key, lon_key)]

    # If not in cache, ask the API
    try:
        # language='en' forces English results (e.g., 'South Korea' instead of '대한민국')
        location = geolocator.reverse(f"{lat}, {lon}", timeout=5, language='en')
        
        if location:
            address = location.raw.get('address', {})
            country = address.get('country', '')

            # Check if the location is in Korea
            # Nominatim usually returns "South Korea", but we check for variations just in case
            if country in ['South Korea', 'Republic of Korea', 'Korea']:
                area = (address.get('county') or 
                        address.get('province') or 
                        "Unknown_Location")
            else:
                # === NEW LOGIC FOR ABROAD (Country Name Only) ===
                # If country is missing (rare), fallback to Unknown
                area = country if country else "Unknown_Location"

            # Save to cache
            location_cache[(lat_key, lon_key)] = area
            return area
            
    except Exception as e:
        print(f"    ! Geocoding warning: {e}")
    
    return "Unknown_Location"


def remDash(name):
    for i in range(len(name)):
        if name[i] == '/':
            return name[:i].strip()
    return name.strip()


def classifyFile(file_path):
    """
    file_path: Path object
    returns 1 for image, 2 for video, 0 for neither
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type and mime_type.startswith('video/'):
        return 2
    elif mime_type and mime_type.startswith('image/'):
        return 1
    return 0


def get_file_creation_year(file_path):
    """Returns the creation year of a file as a string."""
    try:
        # getctime returns a float timestamp (seconds since epoch)
        creation_timestamp = os.path.getctime(file_path)
        dt_object = datetime.fromtimestamp(creation_timestamp)
        # Return just the year
        return str(dt_object.year)
    except Exception as e:
        print(f"Error getting date for {file_path}: {e}")
        return "0000_NoDate"


def categImg(folder_path):
    """
    Scans folder from folder_path and organizes photos into Year/Location format
    folder_path: str
    """
    # Convert strings to Path objects
    source_dir = Path(folder_path)
    supported_extensions = ('.jpg', '.jpeg', '.png')

    print(f"--- Organizing photos from: '{source_dir}' ---")

    if not source_dir.exists():
        print(f"Error: Source folder '{source_dir}' not found.")
        return

    for file_path in source_dir.iterdir():
        if classifyFile(file_path) == 2:
            year = get_file_creation_year(file_path)
            imageID = extractImageID(str(file_path))
            testPath = source_dir / year / 'Videos'
            if testPath.exists():
                print(f"  -> Detected: {year} / Videos")
                moveFolder(imageID, source_dir, testPath)
            else:
                print(f"  -> Making {year} / Videos")
                target_folder = makeFolder(source_dir, year, 'Videos')
                moveFolder(imageID, source_dir, testPath)
            continue
        
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
                imageID = extractImageID(str(file_path))
                location_name = remDash(get_location_name(lat, lon))
                testPath = source_dir / year / location_name
                if testPath.exists():
                    print(f"  -> Detected: {year} / {location_name}")
                    moveFolder(imageID, source_dir, testPath)
                else:
                    target_folder = makeFolder(source_dir, year, location_name)
                    moveFolder(imageID, source_dir, testPath)
            else:
                # No Location data
                print(f"  -> No GPS. Not performing anything")
        else:
            # No EXIF data at all
            print(f"  -> No EXIF detected for {file_path}")


def isImportantImg(image_path):
    """
    Input: str
    Reads an image located in 'image_path' and filters it into:
    -> 'Important'
    -> 'Nonessential' - Blurry, Screenshot/Digital, Document/Receipt
    """
    # 0. Load Image
    img = cv2.imread(image_path)
    if img is None:
        return False

    # 1. Initialize all variables required for testing
    
    # --- FILTER 1: BLUR DETECTION (Laplacian Variance) ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    # --- FILTER 2: SCREENSHOT DETECTION (Unique Color Count) ---
    small_img = cv2.resize(img, (100, 100), interpolation=cv2.INTER_NEAREST)
    pixels = small_img.reshape(-1, 3)
    unique_colors = len(np.unique(pixels, axis=0))
    # --- FILTER 3: RECEIPT/DOCUMENT DETECTION (Saturation & Edges) ---
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mean_saturation = hsv[:, :, 1].mean()
    # Check Edge Density (Text creates dense edges)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / edges.size

    # 2. Assign appropriate threshold for each filters and assess the images
    if (blur_score < 100 or unique_colors < 2000 or 
            (mean_saturation < 30 and edge_density > 0.10)):
        return False

    # 3. If passed all tests, indicate as an important image
    return True


def filterImage(basePath, goodPath, badPath):
    """
    basePath: Path object
    goodPath: Path object
    badPath: Path object
    Reads an image located in 'image_path' and filters it into:
    -> 'Important'
    -> 'Nonessential' - Blurry, Screenshot/Digital, Document/Receipt
    """
    for child in basePath.iterdir(): 
        imageID = str(child)
        imagefileID = extractImageID(imageID)
        if classifyFile(child) == 2 or isImportantImg(imageID):
            moveFolder(imagefileID, basePath, goodPath)
        else:
            moveFolder(imagefileID, basePath, badPath)
    return


# --- DEMO USAGE ---
# current_dir = Path.cwd()
# parent_dir = current_dir.parent
# basePath = parent_dir / 'Temp'
# goodPath = parent_dir / 'Photos'
# badPath = parent_dir / 'NONESSENTIAL'

# filterImage(basePath, goodPath, badPath)
# print(f"  -> Completed filtering. Moving to categorizing")
# categImg(goodPath)