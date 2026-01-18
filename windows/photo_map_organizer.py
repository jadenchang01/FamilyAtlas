# ============================================================================
# MAIN WINDOW - Based on page.tsx structure
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

from widgets.sidebar import Sidebar
from widgets.map_widget import MapWidget
from widgets.location_dashboard import LocationDashboard
from workers.image_processing_thread import ImageProcessingThread
from models.data_models import LocationGroup

class PhotoMapOrganizer(QMainWindow):
    
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
    
    def _on_processing_complete(self, locations: list[LocationGroup], progress: QProgressDialog):
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
        
        # Find the photo object to get its file path
        photo_to_delete = None
        for photo in location.photos:
            if photo.id == photo_id:
                photo_to_delete = photo
                break
        
        if photo_to_delete is None:
            print(f"Warning: Photo {photo_id} not found in location {location_id}")
            return
        
        # Delete the actual file from disk, we will move it back into Nonessentials for now
        try:
            file_path = Path(photo_to_delete.url)
            if file_path.exists():
                shutil.move(str(file_path), ('NONESSENTIAL/'+str(photo_id)))
                print(f"✓ Deleted file: {file_path}")
            else:
                print(f"Warning: File not found: {file_path}")
        except Exception as e:
            # Show error to user if deletion fails
            QMessageBox.warning(
                self,
                "Deletion Failed",
                f"Could not delete file:\n{photo_to_delete.url}\n\nError: {str(e)}"
            )
            return  # Don't update UI if file deletion failed
        
        # Remove photo from location (only if file deletion succeeded)
        location.photos = [p for p in location.photos if p.id != photo_id]
        
        # Update map pin count
        self.map_widget.update_pin_count(location_id, len(location.photos))
        
        # If no photos left, remove location entirely
        if len(location.photos) == 0:
            del self.locations[location_id]
            self.map_widget.remove_pin(location_id)
            self.sidebar.clear_locations()
            for loc in self.locations.values():
                self.sidebar.add_location_item(loc)
            
            # Optional: Remove empty folder
            try:
                if location.folder_path and location.folder_path.exists():
                    location.folder_path.rmdir()  # Only removes if empty
                    print(f"✓ Removed empty folder: {location.folder_path}")
            except Exception as e:
                print(f"Note: Could not remove folder {location.folder_path}: {e}")