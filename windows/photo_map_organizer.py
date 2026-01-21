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
        
        # Application state
        self.locations: Dict[str, LocationGroup] = {}
        self.selected_location: Optional[LocationGroup] = None
        self.is_dashboard_open = False
        self.is_loading = False
        
        # Base path for photo organization
        self.base_path = Path('')
        
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
        
        # Sidebar trigger
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
        
        # Save button
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background: hsl(21, 66%, 68%);
                color: hsl(24, 50%, 10%);
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: hsl(21, 66%, 60%);
            }
        """)
        save_btn.clicked.connect(self.manual_save)
        layout.addWidget(save_btn)
        
        # Load button
        load_btn = QPushButton("📂 Load")
        load_btn.setStyleSheet("""
            QPushButton {
                background: hsl(42, 63%, 80%);
                color: hsl(24, 50%, 10%);
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: hsl(42, 63%, 70%);
            }
        """)
        load_btn.clicked.connect(self.manual_load)
        layout.addWidget(load_btn)
        
        return bar


    def manual_save(self):
        """Manual save triggered by button"""
        success = self.save_progress()
        if success:
            QMessageBox.information(
                self,
                "Saved",
                f"Progress saved successfully!\n\n"
                f"Locations: {len(self.locations)}\n"
                f"Photos: {sum(len(loc.photos) for loc in self.locations.values())}"
            )    
    

    def manual_load(self):
        """Manual load triggered by button"""
        if len(self.locations) > 0:
            reply = QMessageBox.question(
                self,
                "Load Data",
                "Loading will replace your current session. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        success = self.load_progress()
        if success:
            QMessageBox.information(
                self,
                "Loaded",
                f"Progress loaded successfully!\n\n"
                f"Locations: {len(self.locations)}\n"
                f"Photos: {sum(len(loc.photos) for loc in self.locations.values())}"
            )


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
            
            # Save new file
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Progress saved: {len(self.locations)} locations, "
                  f"{save_data['total_photos']} photos")
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
            print(f"Loading save file version: {version}")
            
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
            
            print(f"✓ Loaded: {total_locations} locations, {total_photos} photos")
            print(f"  Last saved: {saved_at}")
            
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
            if success:
                # Optional: Show notification
                print("Previous session restored")
        else:
            print("Starting fresh - no previous save found")
    

    def prompt_save_on_changes(self):
        """
        Prompt user to save if there are unsaved changes
        Call this before closing or major operations
        """
        if len(self.locations) > 0:
            reply = QMessageBox.question(
                self,
                "Save Changes?",
                "Do you want to save your current progress?",
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                return self.save_progress()
            elif reply == QMessageBox.StandardButton.Cancel:
                return None  # Cancel the operation
            else:
                return True  # Continue without saving
        return True


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
        """Handle photo deletion"""
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
        
        # Delete the actual file from disk
        try:
            file_path = Path(photo_to_delete.url)
            if file_path.exists():
                file_path.unlink()
                print(f"✓ Deleted file: {file_path}")
            else:
                print(f"Warning: File not found: {file_path}")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Deletion Failed",
                f"Could not delete file:\n{photo_to_delete.url}\n\nError: {str(e)}"
            )
            return
        
        # Remove photo from location
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
            
            # Remove empty folder
            try:
                if location.folder_path and location.folder_path.exists():
                    location.folder_path.rmdir()
                    print(f"✓ Removed empty folder: {location.folder_path}")
            except Exception as e:
                print(f"Note: Could not remove folder {location.folder_path}: {e}")
        
        # AUTO-SAVE after deletion
        self.save_progress()


    def closeEvent(self, event):
        """Handle application closing"""
        # Auto-save before closing
        if len(self.locations) > 0:
            self.save_progress()
            print("Progress saved before closing")
        
        event.accept()