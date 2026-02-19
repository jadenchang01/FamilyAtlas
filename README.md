# 🌍 Family Atlas - Photo Map Organizer

Family Atlas breathes life into photo archives. It provides a desktop solution that automatically transforms messy gallery into a structured, interactive recollection of family trips.


## 📸 What It Does

Family Atlas helps you rediscover your photo memories by removing trivial images and automatically organizing the rest by time and location. Simply point the app to a folder of photos, and it will:

1. **Filter non-essential images** (blurry photos, screenshots, notes)
2. **Extract Meta Data** from photo EXIF data
3. **Group photos by location** (city/town level)
4. **Organize directory by year and location** for easy navigation
5. **Display on interactive map** with clickable pins


## ✨ Features

### 🗺️ Interactive Map View
- Beautiful Leaflet-based map with custom markers
- Click pins to view all photos from that location
- Visual representation of your travel history

### 📁 Smart Organization
- Automatic folder structure: `Photos/Year/Location/`
- GPS-based location detection using reverse geocoding
- Intelligent filtering of non-essential images

### 🖼️ Photo Management
- Grid gallery view with hover effects
- Bulk photo selection and deletion
- Location renaming and editing


## 🚀 Installation

**For macOS (recommended):**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install PyQt5 PyQtWebEngine pillow opencv-python geopy
```

**For Windows:**
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install PyQt5 PyQtWebEngine pillow opencv-python geopy
```


## 🏗️ Project Structure

```
family-atlas/
│
├── main.py
│   → Application entry point that initializes Qt and launches the main window
│
├── models/
│   └── data_models.py
│       → Defines Photo and LocationGroup classes with save/load serialization
│
├── workers/
│   └── image_processing_thread.py
│       → Background thread that processes images, extracts GPS data, and organizes photos by location
│
├── widgets/
│   ├── map_widget.py
│   │   → Interactive Leaflet map with Python-JavaScript bridge for displaying location pins
│   ├── gallery_image_card.py
│   │   → Individual photo card widget with hover effects, selection, and delete functionality
│   ├── location_dashboard.py
│   │   → Modal dialog for managing photos within a location, including subfolder navigation
│   └── sidebar.py
│       → Collapsible navigation panel displaying location list and upload button
│
├── windows/
│   └── photo_map_organizer.py
│       → Main application window managing state, event handlers, and save/load operations
│
├── backend/
│   └── readImage.py
│       → Image processing functions for EXIF extraction, GPS parsing, and photo filtering
│
├── requirements.txt
│   → Python package dependencies required to run the application
│
└── README.md
│   → Project documentation with installation instructions and usage guide
│
└── Photos/
|   → Organized photos, the structure below is an example
|   ├── 2023/               
|       ├── Tokyo/
|       └── Paris/
|       ...
|   ├── 2024/
|       └── Seoul/
|       ...
|   └── NONESSENTIAL/
|   → Filtered out images
```


## 🙏 References

- [OpenCV](https://pypi.org/project/opencv-python/) - Image processing
- [Pillow](https://python-pillow.org/) - Meta Data(EXIF) extraction
- [GeoPy](https://geopy.readthedocs.io/) - Geocoding library
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [Leaflet](https://leafletjs.com/) - Interactive map library
- [OpenStreetMap](https://www.openstreetmap.org/) - Map tile provider


## 📧 Contact

Email: chang.ihj05@gmail.com
