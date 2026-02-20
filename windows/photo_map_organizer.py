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
from backend.readImage import moveFolder, classifyFile

class PhotoMapOrganizer(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Family Atlas - Photo Map Organizer")
        self.setGeometry(100, 100, 1400, 900)
        
        # Application state
        self.locations: Dict[str, LocationGroup] = {}
        self.selected_location: Optional[LocationGroup] = None
        self.is_dashboard_open = False
        self.is_loading = False
        
        # Defines base path for photo organization, so we determine if running as executable (frozen) or script
        if getattr(sys, 'frozen', False):
            # If frozen (PyInstaller), we assume executable file is in the same level as Photos 
            application_path = Path(sys.executable).parent
        else:
            # If dev (script), use project root (assuming inside windows/ folder)
            application_path = Path(__file__).parent.parent

        self.base_path = application_path
        
        # Save file path
        self.save_file = self.base_path / "models" / "app_data.json"
        
        self.setup_ui()
        self.setup_connections()
        
        # AUTO-LOAD on startup
        self.auto_load_on_startup()
        
        # Apply global stylesheet
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
        """Create top navigation bar with Save/Load buttons"""
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
        
        # Title
        title = QLabel("MAP")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: hsl(24, 20%, 15%);
            letter-spacing: 1px;
            font-family: 'Arial Black', sans-serif;
        """)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Sync button
        sync_btn = QPushButton("🔄 Sync")
        sync_btn.setStyleSheet("""
            QPushButton {
                background: hsl(200, 63%, 80%);
                color: hsl(200, 50%, 10%);
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: hsl(200, 63%, 70%);
            }
        """)
        sync_btn.clicked.connect(self.handle_sync)
        layout.addWidget(sync_btn)

        return bar


    def setup_connections(self):
        """Connect signals and slots - matches page.tsx event handlers"""
        # Upload button connection
        self.sidebar.upload_btn.clicked.connect(self.handle_image_processing)
        
        # Map interactions
        self.map_widget.pinSelected.connect(self.handle_marker_click)
        
        # Sidebar location selection
        self.sidebar.locationSelected.connect(self.handle_marker_click)


    #save&load mechanisms
    def save_progress(self) -> bool:
        """
        Save current application state to JSON file
        Called automatically after any change
        """
        try:
            # Prepare data structure
            save_data = {
                "version": "1.0.0",
                "saved_at": datetime.now().isoformat(),
                "base_path": str(self.base_path),
                "locations": {
                    loc_id: location.to_dict() 
                    for loc_id, location in self.locations.items()
                },
                "total_locations": len(self.locations),
                "total_photos": sum(len(loc.photos) for loc in self.locations.values())
            }
            
            # Write to file with backup
            if self.save_file.exists():
                # Create backup of existing file
                backup_file = self.save_file.with_suffix('.json.backup')
                self.save_file.rename(backup_file)
            
            # Ensure directory exists
            self.save_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save new file
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            # print(f"✓ Progress saved: {len(self.locations)} locations, "
            #       f"{save_data['total_photos']} photos")
            return True
            
        except Exception as e:
            print(f"✗ Save failed: {e}")
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Could not save progress:\n{str(e)}"
            )
            return False


    def load_progress(self) -> bool:
        """
        Load application state from JSON file
        Returns True if successful, False otherwise
        """
        if not self.save_file.exists():
            print("No saved data found")
            return False
        
        try:
            # Read save file
            with open(self.save_file, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            # Verify version compatibility
            version = save_data.get("version", "unknown")
            
            # Clear existing data
            self.locations.clear()

            # Load locations
            locations_data = save_data.get("locations", {})
            for loc_id, loc_dict in locations_data.items():
                location = LocationGroup.from_dict(loc_dict)
                self.locations[loc_id] = location
            
            # Update UI
            self.update_ui_from_loaded_data()
            
            # Show success message
            total_locations = save_data.get("total_locations", 0)
            total_photos = save_data.get("total_photos", 0)
            saved_at = save_data.get("saved_at", "unknown")
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"✗ Invalid save file format: {e}")
            QMessageBox.warning(
                self,
                "Load Failed",
                f"Save file is corrupted or invalid:\n{str(e)}"
            )
            return False
        except Exception as e:
            print(f"✗ Load failed: {e}")
            QMessageBox.warning(
                self,
                "Load Failed",
                f"Could not load saved data:\n{str(e)}"
            )
            return False


    def update_ui_from_loaded_data(self):
        """Update UI components after loading data"""
        # Clear sidebar
        self.sidebar.clear_locations()
        
        # Add locations to sidebar
        for location in self.locations.values():
            self.sidebar.add_location_item(location)
        
        # Add pins to map
        for location in self.locations.values():
            if location.lat != 0.0 and location.lng != 0.0:
                self.map_widget.add_pin(
                    location.id,
                    location.lat,
                    location.lng,
                    location.name,
                    len(location.photos)
                )
        return


    def auto_load_on_startup(self):
        """Automatically load saved data when app starts"""
        if self.save_file.exists():
            success = self.load_progress()
        else:
            pass


    def handle_sync(self):
        """Re-scan folder structure without re-filtering images"""
        # sets syncPath to iterate through the photos folder
        syncPath = self.base_path / 'Photos'
        
        # Show progress dialog
        progress = QProgressDialog("Syncing folder structure...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Syncing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Create and start processing thread in scan_only mode
        self.processing_thread = ImageProcessingThread(syncPath, syncPath, mode='scan_only')
        self.processing_thread.progressUpdate.connect(
            lambda value, msg: (progress.setValue(value), progress.setLabelText(msg))
        )
        self.processing_thread.processingComplete.connect(
            lambda locations: self._on_processing_complete(locations, progress)
        )
        self.processing_thread.start()


    def handle_image_processing(self):
        """Handle image upload and processing - matches handleImageProcessing"""
        # Allows users to select folder to work with
        sourceFolder = QFileDialog.getExistingDirectory(
            self,
            "Select Photo Folder",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        if not sourceFolder:
            return
        
        # Determine base path for portability
        # The user selects the folder to organize (or where images are).
        
        # SAFETY CHECK: Ensure all files are images or videos
        sourcePath = Path(sourceFolder)
        try:
             invalid_files = []
             for item in sourcePath.iterdir():
                 if item.name.startswith('.'): # Ignore hidden files
                     continue
                 
                 file_type = classifyFile(item)
                 if file_type == 0:
                     invalid_files.append(item.name)
             
             if invalid_files:
                 msg = "Safety Alert: This folder contains non-media files:\n\n"
                 msg += "\n".join(invalid_files[:5])
                 if len(invalid_files) > 5:
                     msg += f"\n...and {len(invalid_files) - 5} others."
                 msg += "\n\nPlease select a folder containing ONLY images or videos."
                 
                 QMessageBox.warning(self, "Safety Check Failed", msg)
                 return
        except Exception as e:
             QMessageBox.warning(self, "Error", f"Error scanning folder: {e}")
             return

        # Show progress dialog
        progress = QProgressDialog("Processing images...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Processing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Create and start processing thread
        # source_folder is also the base_path in this logic, or we could ask for source separately.
        # Assuming the user selects the root folder containing unorganized images
        self.processing_thread = ImageProcessingThread(sourcePath, self.base_path)
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
        self.map_widget.clear_pins()
        for location in locations:
            if location.lat != 0.0 and location.lng != 0.0:
                self.map_widget.add_pin(
                    location.id,
                    location.lat,
                    location.lng,
                    location.name,
                    len(location.photos)
                )
        
        # AUTO-SAVE after processing
        self.save_progress()
        
        QMessageBox.information(
            self,
            "Processing Complete",
            f"Successfully organized {len(locations)} locations with "
            f"{sum(len(loc.photos) for loc in locations)} photos!\n\n"
            f"Progress automatically saved."
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
        """Handle location update"""
        self.locations[updated_location.id] = updated_location
        
        # Update map pin
        self.map_widget.update_pin_count(
            updated_location.id,
            len(updated_location.photos)
        )
        
        # AUTO-SAVE after location update
        self.save_progress()
    

    def handle_delete_photo(self, location_id: str, photo_id: str):
        """Handle photo deletion - file has already been moved by location_dashboard.
        This method only updates the in-memory data model and the UI."""
        if location_id not in self.locations:
            return
        
        location = self.locations[location_id]
        
        # Remove photo from location (file move was already done in location_dashboard)
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
            
            # Remove empty folder (clean up macOS .DS_Store / hidden files first)
            try:
                if location.folder_path and location.folder_path.exists():
                    for hidden in location.folder_path.iterdir():
                        if hidden.name.startswith('.'):
                            hidden.unlink(missing_ok=True)
                    location.folder_path.rmdir()
            except Exception as e:
                print(f"Note: Could not remove folder {location.folder_path}: {e}")
        
        # AUTO-SAVE after deletion
        self.save_progress()


    def closeEvent(self, event):
        """Handle application closing"""
        # Auto-save before closing
        if len(self.locations) > 0:
            self.save_progress()
            # print("Progress saved before closing")
        
        event.accept()