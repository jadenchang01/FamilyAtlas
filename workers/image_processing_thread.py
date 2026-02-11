# ============================================================================
# IMAGE PROCESSING THREAD
# ============================================================================

import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QScrollArea,
    QSplitter, QFrame, QGridLayout, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QToolButton, QSizePolicy, QProgressDialog
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QObject, QSize, QTimer, QThread
)
from PyQt5.QtGui import QPixmap, QIcon, QImage, QPalette, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from backend.readImage import categImg, filterImage, get_exif_data, get_lat_lon
from models.data_models import Photo, LocationGroup

class ImageProcessingThread(QThread):
    """Background thread for processing images"""
    
    progressUpdate = pyqtSignal(int, str)  # progress, status message
    processingComplete = pyqtSignal(list)  # List of LocationGroup objects
    
    def __init__(self, source_folder: Path, base_path: Path, mode: str = 'full'):
        super().__init__()
        self.source_folder = source_folder
        self.base_path = base_path
        self.mode = mode
    
    def run(self):
        """Process images in background"""
        try:
            if self.mode == 'full':
                self.progressUpdate.emit(10, "Filtering images...")
                
                #defines the good and bad path for the filtered images to be categorized
                goodPath = self.base_path / 'Photos'
                badPath = self.base_path / 'Photos' / 'NONESSENTIAL'

                filterImage(self.source_folder, goodPath, badPath)
                
                self.progressUpdate.emit(30, "Categorizing by location...")
                
                # Use backend categImg to sort into locations
                categImg(str(goodPath))
            
            self.progressUpdate.emit(80, "Scanning location groups...")
            
            # Scan organized photos and create LocationGroup objects
            # We scan the 'Photos' directory which should be at self.base_path / 'Photos'
            # If mode is scan_only, we assume base_path IS the root containing 'Photos', or is 'Photos' itself?
            # Standardizing: self.base_path is the parent of 'Photos' usually.
            
            goodPath = self.base_path / 'Photos'
            if not goodPath.exists():
                # Fallback if user selected the Photos folder directly
                if self.base_path.name == 'Photos':
                    goodPath = self.base_path
            
            locations = self._scan_organized_photos(goodPath)
            
            self.progressUpdate.emit(100, "Complete!")
            self.processingComplete.emit(locations)
            
        except Exception as e:
            print(f"Error processing images: {e}")
            self.processingComplete.emit([])
    
    def _scan_organized_photos(self, photos_path):
        """Scan organized photos and create LocationGroup objects"""
        locations = []
        
        if not photos_path.exists():
            return locations
        
        # Iterate through year folders
        for year_dir in photos_path.iterdir():
            if not year_dir.is_dir() or year_dir.name == 'NONESSENTIAL':
                continue
                
            year = year_dir.name
            
            # Iterate through location folders
            for location_dir in year_dir.iterdir():
                if not location_dir.is_dir():
                    continue
                
                location_name = location_dir.name
                
                # RECURSIVE SCAN using rglob to find all images in subfolders too
                extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
                image_files = []
                for ext in extensions:
                    image_files.extend(location_dir.rglob(ext))
                
                if not image_files:
                    continue
                
                # Try to get coordinates from first image
                lat, lng = 0.0, 0.0
                first_image = image_files[0]
                exif_data = get_exif_data(str(first_image))
                if exif_data:
                    lat, lng = get_lat_lon(exif_data)
                    if lat is None or lng is None:
                        lat, lng = 0.0, 0.0
                
                # Create LocationGroup
                location_id = f"{year}_{location_name}".replace(" ", "_")
                location_group = LocationGroup(
                    id=location_id,
                    name=f"{location_name} ({year})",
                    lat=lat,
                    lng=lng,
                    year=year
                )
                location_group.folder_path = location_dir
                
                # Add photos
                for img_file in image_files:
                    photo = Photo(
                        id=img_file.name,
                        name=img_file.name,
                        url=str(img_file),
                        hint=""
                    )
                    location_group.photos.append(photo)
                
                locations.append(location_group)
        
        return locations