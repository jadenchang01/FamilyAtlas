# 🌍 Family Atlas - Photo Map Organizer

Family Atlas breathes life into forgotten photo archives. It provides a desktop solution that automatically transforms thousands of disorganized images into a structured, interactive journey through time and geography.


## 📸 What It Does

Family Atlas helps you rediscover your photo memories by removing trivial images and automatically organizing the rest geographically. Simply point the app to a folder of photos, and it will:

1. **Filter non-essential images** (blurry photos, screenshots, receipts)
2. **Extract GPS coordinates** from photo EXIF data
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
- Photo count tracking per location

### 🎨 Modern Design
- Clean, warm color scheme
- Responsive sidebar navigation
- Smooth animations and transitions
- Cross-platform compatibility


## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- macOS, Windows, or Linux

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/family-atlas.git
cd family-atlas
```

### Step 2: Install Dependencies

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

### Step 3: Run the Application

```bash
python main.py
```


## 🏗️ Project Structure

```
family-atlas/
├── main.py                 # Main application entry point
├── readImage.py            # Backend image processing logic
├── README.md               # This file
├── requirements.txt        # Python dependencies
└── Photos/                 # Organized photos, the structure below is an example
    ├── 2023/               
        ├── Tokyo/
        └── Paris/
        ...
    └── 2024/
        └── Seoul/
        ...
└── NONESSENTIAL/           # Filtered out images
├── Temp/                   # Temporary folder containing images before import
```


## 🛠️ Technical Details

### User Flow

```
User selects folder
       ↓
ImageProcessingThread starts
       ↓
Extract EXIF data → Get GPS → Reverse geocode → Organize files
       ↓
Create LocationGroup objects
       ↓
Update UI (map pins, sidebar, galleries)
       ↓
Ready for user interaction
```

### Image Filtering

The app automatically filters out:
- **Blurry images** (Laplacian variance < 100)
- **Screenshots** (low unique color count < 2000)
- **Documents/Receipts** (low saturation + high edge density)


## 🙏 References
- [OpenCV](https://pypi.org/project/opencv-python/) - Image processing
- [Pillow](https://python-pillow.org/) - Image processing II
- [GeoPy](https://geopy.readthedocs.io/) - Geocoding library
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [Leaflet](https://leafletjs.com/) - Interactive map library
- [OpenStreetMap](https://www.openstreetmap.org/) - Map tile provider


## 📧 Contact

Email: chang.ihj05@gmail.com
