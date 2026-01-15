"""
Photo Map Organizer - PyQt6 Desktop Application
Translates TypeScript/React design to Python/PyQt6
Based on page.tsx structure with Sidebar, Map, and Location Dashboard
"""

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

# Import backend functions
from readImage import (
    makeFolder, moveFolder, get_exif_data, get_lat_lon,
    get_location_name, categImg, filterImage, isImportantImg
)


# ============================================================================
# DATA MODELS
# ============================================================================

class Photo:
    """Represents a single photo"""
    def __init__(self, id: str, name: str, url: str, hint: str = ""):
        self.id = id
        self.name = name
        self.url = url  # File path
        self.hint = hint
        

class LocationGroup:
    """Represents a location with associated photos"""
    def __init__(self, id: str, name: str, lat: float, lng: float, year: str):
        self.id = id
        self.name = name
        self.lat = lat
        self.lng = lng
        self.year = year
        self.photos: List[Photo] = []
        self.folder_path: Optional[Path] = None


# ============================================================================
# IMAGE PROCESSING THREAD
# ============================================================================

class ImageProcessingThread(QThread):
    """Background thread for processing images"""
    
    progressUpdate = pyqtSignal(int, str)  # progress, status message
    processingComplete = pyqtSignal(list)  # List of LocationGroup objects
    
    def __init__(self, source_folder: Path, base_path: Path):
        super().__init__()
        self.source_folder = source_folder
        self.base_path = base_path
    
    def run(self):
        """Process images in background"""
        try:
            self.progressUpdate.emit(10, "Filtering images...")
            
            #defines the good and bad path for the filtered images to be categorized
            goodPath = self.base_path / 'Photos'
            badPath = self.base_path / 'NONESSENTIAL'

            filterImage(self.source_folder, goodPath, badPath)
            
            self.progressUpdate.emit(30, "Categorizing by location...")
            
            # Use backend categImg to sort into locations
            categImg(str(goodPath))
            
            self.progressUpdate.emit(80, "Building location groups...")
            
            # Scan organized photos and create LocationGroup objects
            locations = self._scan_organized_photos(goodPath)
            
            self.progressUpdate.emit(100, "Complete!")
            self.processingComplete.emit(locations)
            
        except Exception as e:
            print(f"Error processing images: {e}")
            self.processingComplete.emit([])
    
    def _scan_organized_photos(self, photos_path: Path) -> List[LocationGroup]:
        """Scan organized photos and create LocationGroup objects"""
        locations = []
        
        if not photos_path.exists():
            return locations
        
        # Iterate through year folders
        for year_dir in photos_path.iterdir():
            if not year_dir.is_dir():
                continue
                
            year = year_dir.name
            
            # Iterate through location folders
            for location_dir in year_dir.iterdir():
                if not location_dir.is_dir():
                    continue
                
                location_name = location_dir.name
                
                # Get first image to extract GPS coordinates
                image_files = list(location_dir.glob("*.jpg")) + list(location_dir.glob("*.jpeg")) + list(location_dir.glob("*.png"))
                
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


# ============================================================================
# MAP BRIDGE - Python <-> JavaScript Communication
# ============================================================================

class MapBridge(QObject):
    """Bridge for Python-JavaScript communication"""
    
    # Signals to emit to main application
    coordinates_clicked = pyqtSignal(float, float)
    pin_clicked = pyqtSignal(str)
    
    @pyqtSlot(float, float)
    def on_map_click(self, lat: float, lng: float):
        """Called from JavaScript when map is clicked"""
        print(f"Map clicked: {lat}, {lng}")
        self.coordinates_clicked.emit(lat, lng)
    
    @pyqtSlot(str)
    def on_pin_click(self, pin_id: str):
        """Called from JavaScript when pin is clicked"""
        print(f"Pin clicked: {pin_id}")
        self.pin_clicked.emit(pin_id)


# ============================================================================
# MAP WIDGET - QWebEngineView with Leaflet
# ============================================================================

class MapWidget(QWebEngineView):
    """Interactive map widget using Leaflet"""
    
    coordinatesClicked = pyqtSignal(float, float)
    pinSelected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setup_web_channel()
        self.load_map()
        
    def setup_web_channel(self):
        """Set up Python-JavaScript bridge"""
        self.channel = QWebChannel()
        self.bridge = MapBridge()
        
        # Connect bridge signals to widget signals
        self.bridge.coordinates_clicked.connect(self.coordinatesClicked.emit)
        self.bridge.pin_clicked.connect(self.pinSelected.emit)
        
        # Register bridge with JavaScript
        self.channel.registerObject('bridge', self.bridge)
        self.page().setWebChannel(self.channel)
    
    def load_map(self):
        """Load HTML page with Leaflet map"""
        html = self._generate_map_html()
        self.setHtml(html)
    
    def add_pin(self, pin_id: str, lat: float, lng: float, title: str, photo_count: int = 0):
        """Add pin to map from Python"""
        js = f"addPin('{pin_id}', {lat}, {lng}, '{title}', {photo_count});"
        self.page().runJavaScript(js)
    
    def remove_pin(self, pin_id: str):
        """Remove pin from map"""
        js = f"removePin('{pin_id}');"
        self.page().runJavaScript(js)
    
    def update_pin_count(self, pin_id: str, count: int):
        """Update photo count for pin"""
        js = f"updatePinCount('{pin_id}', {count});"
        self.page().runJavaScript(js)
    
    def center_map(self, lat: float, lng: float, zoom: int = 10):
        """Center map on coordinates"""
        js = f"map.setView([{lat}, {lng}], {zoom});"
        self.page().runJavaScript(js)
    
    def _generate_map_html(self) -> str:
        """Generate HTML with Leaflet map - matches your design colors"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body { 
            margin: 0; 
            padding: 0; 
            background: hsl(28, 80%, 96%);
        }
        #map { 
            height: 100vh; 
            width: 100vw; 
        }
        .custom-popup {
            font-family: Helvetica Neue;
        }
        .custom-popup .location-name {
            font-weight: 600;
            color: hsl(24, 20%, 15%);
            margin-bottom: 4px;
        }
        .custom-popup .photo-count {
            font-size: 12px;
            color: hsl(24, 15%, 45%);
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map
        var map = L.map('map').setView([37.7749, -122.4194], 4);
        
        // Add tile layer - warm color scheme matching your design
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Store markers
        var markers = {};
        
        // Custom marker icon matching your design
        var customIcon = L.divIcon({
            className: 'custom-marker',
            html: '<div style="background: hsl(21, 66%, 68%); width: 30px; height: 30px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
        
        // Initialize Qt WebChannel
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            
            // Handle map clicks
            map.on('click', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                bridge.on_map_click(lat, lng);
            });
        });
        
        // Add pin function (called from Python)
        function addPin(pinId, lat, lng, title, photoCount) {
            // Remove existing marker if present
            if (markers[pinId]) {
                map.removeLayer(markers[pinId]);
            }
            
            var marker = L.marker([lat, lng], {icon: customIcon}).addTo(map);
            
            var popupContent = '<div class="custom-popup"><div class="location-name">' + title + '</div><div class="photo-count">' + photoCount + ' photos</div></div>';
            marker.bindPopup(popupContent);
            
            marker.on('click', function() {
                bridge.on_pin_click(pinId);
            });
            
            markers[pinId] = marker;
        }
        
        function removePin(pinId) {
            if (markers[pinId]) {
                map.removeLayer(markers[pinId]);
                delete markers[pinId];
            }
        }
        
        function updatePinCount(pinId, count) {
            if (markers[pinId]) {
                var popup = markers[pinId].getPopup();
                if (popup) {
                    var content = popup.getContent();
                    var titleMatch = content.match(/<div class="location-name">(.*?)<\\/div>/);
                    if (titleMatch) {
                        var title = titleMatch[1];
                        var popupContent = '<div class="custom-popup"><div class="location-name">' + title + '</div><div class="photo-count">' + count + ' photos</div></div>';
                        markers[pinId].setPopupContent(popupContent);
                    }
                }
            }
        }
    </script>
</body>
</html>
"""


# ============================================================================
# GALLERY IMAGE CARD - Matches gallery-image-card.tsx
# ============================================================================

class GalleryImageCard(QFrame):
    """Individual photo card with hover effects and actions"""
    
    deleteRequested = pyqtSignal(str)  # photo_id
    selectionChanged = pyqtSignal(str, bool)  # photo_id, is_selected
    
    def __init__(self, photo: Photo, parent=None):
        super().__init__(parent)
        self.photo = photo
        self.is_selected = False
        self.setup_ui()
        
    def setup_ui(self):
        """Set up card UI matching TypeScript design"""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            GalleryImageCard {
                background: hsl(28, 80%, 94%);
                border: 1px solid hsl(28, 70%, 88%);
                border-radius: 8px;
            }
            GalleryImageCard:hover {
                border: 1px solid hsl(21, 66%, 68%);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Image container
        image_container = QWidget()
        image_container.setFixedSize(300, 225)
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setScaledContents(True)
        self.image_label.setFixedSize(300, 225)
        
        # Load image
        pixmap = QPixmap(self.photo.url)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                300, 225, 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        
        image_layout.addWidget(self.image_label)
        
        # Overlay widget (shown on hover)
        self.overlay = QWidget(image_container)
        self.overlay.setStyleSheet("background: rgba(0, 0, 0, 0.2);")
        self.overlay.setFixedSize(300, 225)
        overlay_layout = QVBoxLayout(self.overlay)
        
        # Top row: checkbox and delete button
        top_row = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                background: rgba(255, 255, 255, 0.8);
                border: 2px solid hsl(24, 15%, 45%);
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: hsl(21, 66%, 68%);
                border: 2px solid hsl(21, 66%, 68%);
            }
        """)
        self.checkbox.stateChanged.connect(self._on_selection_changed)
        top_row.addWidget(self.checkbox)
        top_row.addStretch()
        
        # Delete button (top right)
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: hsl(0, 84.2%, 60.2%);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: hsl(0, 84.2%, 50%);
            }
        """)
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.photo.id))
        top_row.addWidget(delete_btn)
        
        overlay_layout.addLayout(top_row)
        overlay_layout.addStretch()
        
        # Info label at bottom
        info_label = QLabel(self.photo.name)
        info_label.setStyleSheet("""
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
        """)
        info_label.setWordWrap(True)
        overlay_layout.addWidget(info_label, alignment=Qt.AlignmentFlag.AlignBottom)
        
        # Position overlay over image
        self.overlay.move(0, 0)
        self.overlay.hide()
        
        layout.addWidget(image_container)
    
    def _on_selection_changed(self, state):
        """Handle checkbox state change"""
        self.is_selected = (state == Qt.CheckState.Checked.value)
        self.selectionChanged.emit(self.photo.id, self.is_selected)
    
    def enterEvent(self, event):
        """Show overlay on hover"""
        self.overlay.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide overlay when not hovering"""
        self.overlay.hide()
        super().leaveEvent(event)


# ============================================================================
# LOCATION DASHBOARD - Matches location-dashboard.tsx (Sheet/Dialog)
# ============================================================================

class LocationDashboard(QDialog):
    """Dashboard for managing location and its photos"""
    
    locationUpdated = pyqtSignal(LocationGroup)
    photoDeleted = pyqtSignal(str, str)  # location_id, photo_id
    
    def __init__(self, location: LocationGroup, parent=None):
        super().__init__(parent)
        self.location = location
        self.selected_photos: Set[str] = set()
        self.is_editing_title = False
        self.setup_ui()
        
    def setup_ui(self):
        """Set up dashboard UI"""
        self.setWindowTitle("Location Dashboard")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QDialog {
                background: hsl(28, 80%, 96%);
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header with editable title
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel(self.location.name)
        self.title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: 600;
            color: hsl(24, 20%, 15%);
        """)
        
        self.title_input = QLineEdit(self.location.name)
        self.title_input.setStyleSheet("""
            font-size: 24px;
            font-weight: 600;
            padding: 4px 8px;
            border: 2px solid hsl(21, 66%, 68%);
            border-radius: 4px;
        """)
        self.title_input.hide()
        
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(32, 32)
        edit_btn.clicked.connect(self._toggle_edit_title)
        
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.title_input)
        header_layout.addWidget(edit_btn)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(f"{len(self.location.photos)} essential photos from this location")
        desc_label.setStyleSheet("color: hsl(24, 15%, 45%); margin-bottom: 8px;")
        layout.addWidget(desc_label)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        new_folder_btn = QPushButton("📁 Create New Folder")
        new_folder_btn.setStyleSheet(self._button_style("outline"))
        new_folder_btn.clicked.connect(self._create_new_folder)
        actions_layout.addWidget(new_folder_btn)
        
        self.delete_selected_btn = QPushButton("🗑️ Delete (0)")
        self.delete_selected_btn.setStyleSheet(self._button_style("destructive"))
        self.delete_selected_btn.clicked.connect(self._delete_selected)
        self.delete_selected_btn.hide()
        actions_layout.addWidget(self.delete_selected_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: hsl(28, 70%, 88%);")
        layout.addWidget(separator)
        
        # Photo gallery scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(gallery_widget)
        self.gallery_layout.setSpacing(16)
        
        # Add photo cards
        self._populate_gallery()
        
        scroll.setWidget(gallery_widget)
        layout.addWidget(scroll, stretch=1)
        
        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self._button_style("secondary"))
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)
        
        layout.addLayout(footer_layout)
    
    def _populate_gallery(self):
        """Populate gallery with photo cards"""
        # Clear existing items
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add photo cards in grid
        row, col = 0, 0
        max_cols = 3
        
        for photo in self.location.photos:
            card = GalleryImageCard(photo)
            card.deleteRequested.connect(self._on_photo_delete)
            card.selectionChanged.connect(self._on_photo_selection_changed)
            
            self.gallery_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def _toggle_edit_title(self):
        """Toggle title editing mode"""
        if not self.is_editing_title:
            self.title_label.hide()
            self.title_input.show()
            self.title_input.setFocus()
            self.is_editing_title = True
        else:
            new_title = self.title_input.text()
            self.location.name = new_title
            self.title_label.setText(new_title)
            self.title_input.hide()
            self.title_label.show()
            self.is_editing_title = False
            self.locationUpdated.emit(self.location)
    
    def _on_photo_selection_changed(self, photo_id: str, is_selected: bool):
        """Handle photo selection changes"""
        if is_selected:
            self.selected_photos.add(photo_id)
        else:
            self.selected_photos.discard(photo_id)
        
        # Update delete button
        if self.selected_photos:
            self.delete_selected_btn.setText(f"🗑️ Delete ({len(self.selected_photos)})")
            self.delete_selected_btn.show()
        else:
            self.delete_selected_btn.hide()
    
    def _on_photo_delete(self, photo_id: str):
        """Handle single photo deletion"""
        reply = QMessageBox.question(
            self, "Delete Photo",
            "Are you sure you want to delete this photo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.photoDeleted.emit(self.location.id, photo_id)
            # Remove from location
            self.location.photos = [p for p in self.location.photos if p.id != photo_id]
            self._populate_gallery()
    
    def _delete_selected(self):
        """Delete all selected photos"""
        if not self.selected_photos:
            return
        
        reply = QMessageBox.question(
            self, "Delete Photos",
            f"Are you sure you want to delete {len(self.selected_photos)} photos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for photo_id in self.selected_photos:
                self.photoDeleted.emit(self.location.id, photo_id)
            
            # Remove from location
            self.location.photos = [p for p in self.location.photos if p.id not in self.selected_photos]
            self.selected_photos.clear()
            self._populate_gallery()
    
    def _create_new_folder(self):
        """Create new folder (placeholder)"""
        QMessageBox.information(self, "New Folder", "New folder created!")
    
    def _button_style(self, variant: str) -> str:
        """Get button style based on variant"""
        styles = {
            "outline": """
                QPushButton {
                    background: white;
                    color: hsl(24, 20%, 15%);
                    border: 1px solid hsl(28, 70%, 88%);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: hsl(6, 100%, 90%);
                }
            """,
            "destructive": """
                QPushButton {
                    background: hsl(0, 84.2%, 60.2%);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: hsl(0, 84.2%, 50%);
                }
            """,
            "secondary": """
                QPushButton {
                    background: hsl(42, 63%, 80%);
                    color: hsl(24, 50%, 10%);
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: hsl(42, 63%, 70%);
                }
            """
        }
        return styles.get(variant, styles["outline"])


# ============================================================================
# SIDEBAR - Matches extended-sidebar.tsx structure
# ============================================================================

class Sidebar(QFrame):
    """Collapsible sidebar matching TypeScript design"""
    
    locationSelected = pyqtSignal(str)  # location_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.location_buttons = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Set up sidebar UI"""
        self.setFixedWidth(288)  # 18rem = 288px
        self.setStyleSheet("""
            Sidebar {
                background: hsl(33, 100%, 93%);
                border-right: 1px solid hsl(28, 70%, 88%);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header - Logo and Title
        header_layout = QHBoxLayout()
        logo_label = QLabel("🌍")
        logo_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(logo_label)
        
        title_label = QLabel("Family Atlas")
        title_label.setStyleSheet("""
            font-size: 20px;
            font-weight: 600;
            color: hsl(24, 20%, 15%);
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setStyleSheet("background: hsl(28, 70%, 88%);")
        layout.addWidget(separator1)
        
        # Body - Image Uploader placeholder
        body_label = QLabel("📤 Image Uploader")
        body_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 500;
            color: hsl(24, 20%, 15%);
            padding: 12px 8px;
        """)
        layout.addWidget(body_label)
        
        # Upload button
        self.upload_btn = QPushButton("Select Photos to Process")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: hsl(21, 66%, 68%);
                color: hsl(24, 50%, 10%);
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: hsl(21, 66%, 60%);
            }
        """)
        layout.addWidget(self.upload_btn)
        
        # Location list scroll area
        self.location_list = QScrollArea()
        self.location_list.setWidgetResizable(True)
        self.location_list.setStyleSheet("border: none;")
        
        list_widget = QWidget()
        self.list_layout = QVBoxLayout(list_widget)
        self.list_layout.setSpacing(4)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.location_list.setWidget(list_widget)
        layout.addWidget(self.location_list, stretch=1)
        
        # Footer
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background: hsl(28, 70%, 88%);")
        layout.addWidget(separator2)
        
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: hsl(24, 20%, 15%);
                border: none;
                text-align: left;
                padding: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: hsl(6, 100%, 90%);
                border-radius: 4px;
            }
        """)
        layout.addWidget(logout_btn)
    
    def add_location_item(self, location: LocationGroup):
        """Add location to sidebar list"""
        item = QPushButton(f"📍 {location.name}\n   {len(location.photos)} photos")
        item.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: hsl(24, 20%, 15%);
                border: none;
                border-radius: 6px;
                padding: 12px;
                text-align: left;
                font-size: 14px;
            }
            QPushButton:hover {
                background: hsl(6, 100%, 90%);
            }
        """)
        item.setMinimumHeight(60)
        item.clicked.connect(lambda: self.locationSelected.emit(location.id))
        
        self.list_layout.addWidget(item)
        self.location_buttons[location.id] = item
        return item
    
    def clear_locations(self):
        """Clear all location items"""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.location_buttons.clear()


# ============================================================================
# MAIN WINDOW - Based on page.tsx structure
# ============================================================================

class PhotoMapOrganizer(QMainWindow):
    """Main application window - matches page.tsx structure"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Family Atlas - Photo Map Organizer")
        self.setGeometry(100, 100, 1400, 900)
        
        # Application state - matches page.tsx state
        self.locations: Dict[str, LocationGroup] = {}
        self.selected_location: Optional[LocationGroup] = None
        self.is_dashboard_open = False
        self.is_loading = False
        
        # Base path for photo organization
        self.base_path = Path('')
        
        self.setup_ui()
        self.setup_connections()
        
        # Apply global stylesheet matching your design
        self.setStyleSheet("""
            QMainWindow {
                background: hsl(28, 80%, 96%);
            }
            * {
                font-family: Helvetica Neue;
            }
        """)
    
    def setup_ui(self):
        """Set up main UI - matches SidebarProvider structure"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create sidebar (matches Sidebar component)
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)
        
        # Main content area (matches SidebarInset)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top bar with trigger and title
        top_bar = self._create_top_bar()
        content_layout.addWidget(top_bar)
        
        # Map area (matches MapView component)
        self.map_widget = MapWidget()
        content_layout.addWidget(self.map_widget, stretch=1)
        
        main_layout.addWidget(content_widget, stretch=1)
    
    def _create_top_bar(self) -> QWidget:
        """Create top navigation bar"""
        bar = QWidget()
        bar.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.5);
                border-bottom: 1px solid hsl(28, 70%, 88%);
            }
        """)
        bar.setFixedHeight(56)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # Sidebar trigger (placeholder - could toggle sidebar)
        trigger_btn = QPushButton("☰")
        trigger_btn.setFixedSize(32, 32)
        trigger_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 20px;
            }
            QPushButton:hover {
                background: hsl(6, 100%, 90%);
                border-radius: 4px;
            }
        """)
        layout.addWidget(trigger_btn)
        
        # Title
        title = QLabel("Photo Map")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: hsl(24, 20%, 15%);")
        layout.addWidget(title)
        
        layout.addStretch()
        
        return bar
    
    def setup_connections(self):
        """Connect signals and slots - matches page.tsx event handlers"""
        # Upload button connection
        self.sidebar.upload_btn.clicked.connect(self.handle_image_processing)
        
        # Map interactions
        self.map_widget.pinSelected.connect(self.handle_marker_click)
        
        # Sidebar location selection
        self.sidebar.locationSelected.connect(self.handle_marker_click)
    
    def handle_image_processing(self):
        """Handle image upload and processing - matches handleImageProcessing"""
        # Allows users to select folder to work with
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Photo Folder",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        
        # Show progress dialog
        progress = QProgressDialog("Processing images...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Processing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Create and start processing thread
        self.processing_thread = ImageProcessingThread(Path(folder), self.base_path)
        self.processing_thread.progressUpdate.connect(
            lambda value, msg: (progress.setValue(value), progress.setLabelText(msg))
        )
        self.processing_thread.processingComplete.connect(
            lambda locations: self._on_processing_complete(locations, progress)
        )
        self.processing_thread.start()
    
    def _on_processing_complete(self, locations: List[LocationGroup], progress: QProgressDialog):
        """Handle completion of image processing"""
        progress.close()
        
        # Update locations dictionary
        self.locations.clear()
        for location in locations:
            self.locations[location.id] = location
        
        # Update sidebar
        self.sidebar.clear_locations()
        for location in locations:
            self.sidebar.add_location_item(location)
        
        # Update map with pins
        for location in locations:
            if location.lat != 0.0 and location.lng != 0.0:
                self.map_widget.add_pin(
                    location.id,
                    location.lat,
                    location.lng,
                    location.name,
                    len(location.photos)
                )
        
        QMessageBox.information(
            self,
            "Processing Complete",
            f"Successfully organized {len(locations)} locations with {sum(len(loc.photos) for loc in locations)} photos!"
        )
    
    def handle_marker_click(self, location_id: str):
        """Handle map marker or sidebar location click - matches handleMarkerClick"""
        if location_id not in self.locations:
            return
        
        self.selected_location = self.locations[location_id]
        self.is_dashboard_open = True
        
        # Open location dashboard
        dashboard = LocationDashboard(self.selected_location, self)
        dashboard.locationUpdated.connect(self.handle_update_location)
        dashboard.photoDeleted.connect(self.handle_delete_photo)
        dashboard.exec()
        
        self.is_dashboard_open = False
        self.selected_location = None
    
    def handle_update_location(self, updated_location: LocationGroup):
        """Handle location update - matches handleUpdateLocation"""
        self.locations[updated_location.id] = updated_location
        
        # Update map pin
        self.map_widget.update_pin_count(
            updated_location.id,
            len(updated_location.photos)
        )
    
    def handle_delete_photo(self, location_id: str, photo_id: str):
        """Handle photo deletion - matches handleDeletePhoto"""
        if location_id not in self.locations:
            return
        
        location = self.locations[location_id]
        
        # Remove photo from location
        location.photos = [p for p in location.photos if p.id != photo_id]
        
        # Update map pin count
        self.map_widget.update_pin_count(location_id, len(location.photos))
        
        # If no photos left, remove location
        if len(location.photos) == 0:
            del self.locations[location_id]
            self.map_widget.remove_pin(location_id)
            self.sidebar.clear_locations()
            for loc in self.locations.values():
                self.sidebar.add_location_item(loc)


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application-wide font
    app.setStyle("Fusion")
    
    # Create and show main window
    window = PhotoMapOrganizer()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()