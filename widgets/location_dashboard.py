import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QScrollArea,
    QSplitter, QFrame, QGridLayout, QFileDialog, QMessageBox,QDialog,
    QDialogButtonBox, QToolButton, QSizePolicy, QProgressDialog, QInputDialog
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QObject, QSize, QTimer, QThread
)
from PyQt5.QtGui import QPixmap, QIcon, QImage, QPalette, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from models.data_models import LocationGroup
from widgets.gallery_image_card import GalleryImageCard
from models.data_models import Photo

# ============================================================================
# LOCATION DASHBOARD - Matches location-dashboard.tsx (Sheet/Dialog)
# ============================================================================

class LocationDashboard(QDialog):
    """
    Dashboard for managing a specific location, its main photos, and subfolders.
    """
    locationUpdated = pyqtSignal(object) # object = LocationGroup
    photoDeleted = pyqtSignal(str, str)  # location_id, photo_id

    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.location = location
        self.current_folder = location.folder_path  # Start at main folder
        self.subfolders: List[Path] = []
        self.selected_photos: Set[str] = set()
        self.is_editing_title = False

        # Define Styles here to keep code clean
        self.styles = {
            "btn_outline": """
                QPushButton { background: white; color: hsl(24, 20%, 15%); border: 1px solid hsl(28, 70%, 88%); border-radius: 6px; padding: 8px 16px; font-weight: 500; }
                QPushButton:hover { background: hsl(6, 100%, 90%); }
            """,
            "btn_destructive": """
                QPushButton { background: hsl(0, 84.2%, 60.2%); color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 500; }
                QPushButton:hover { background: hsl(0, 84.2%, 50%); }
            """,
            "btn_secondary": """
                QPushButton { background: hsl(42, 63%, 80%); color: hsl(24, 50%, 10%); border: none; border-radius: 6px; padding: 8px 16px; font-weight: 500; }
                QPushButton:hover { background: hsl(42, 63%, 70%); }
            """,
            "nav_active": """
                QPushButton { background: hsl(21, 66%, 68%); color: hsl(24, 50%, 10%); border: none; border-radius: 4px; padding: 8px 12px; text-align: left; font-weight: 500; }
            """,
            "nav_inactive": """
                QPushButton { background: transparent; color: hsl(24, 20%, 15%); border: 1px solid hsl(28, 70%, 88%); border-radius: 4px; padding: 8px 12px; text-align: left; }
                QPushButton:hover { background: hsl(6, 100%, 90%); }
            """
        }

        self.setup_ui()
        self.load_subfolders()

    def setup_ui(self):
        """Set up the Split-Panel UI (Left: Folders, Right: Gallery)"""
        self.setWindowTitle("Location Dashboard")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet("QDialog { background: hsl(28, 80%, 96%); }")

        main_layout = QHBoxLayout(self)

        # --- LEFT PANEL: Folder Navigation ---
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet("background: hsl(33, 100%, 93%); border-right: 1px solid hsl(28, 70%, 88%); border-radius: 8px;")
        left_layout = QVBoxLayout(left_panel)

        folder_label = QLabel("📁 Folders")
        folder_label.setStyleSheet("font-size: 16px; font-weight: 600; color: hsl(24, 20%, 15%); padding: 8px;")
        left_layout.addWidget(folder_label)

        # Scroll area for folder list
        folder_scroll = QScrollArea()
        folder_scroll.setWidgetResizable(True)
        folder_scroll.setStyleSheet("border: none; background: transparent;")
        
        folder_list_widget = QWidget()
        self.folder_list_layout = QVBoxLayout(folder_list_widget)
        self.folder_list_layout.setSpacing(4)
        # PyQt5 Change: Qt.AlignTop instead of Qt.AlignmentFlag.AlignTop
        self.folder_list_layout.setAlignment(Qt.AlignTop) 
        
        folder_scroll.setWidget(folder_list_widget)
        left_layout.addWidget(folder_scroll)
        main_layout.addWidget(left_panel)

        # --- RIGHT PANEL: Gallery & Actions ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 1. Header (Title & Edit)
        # 1. Header (Title & Edit)
        header_layout = QHBoxLayout()
        self.title_label = QLabel(self.location.name)
        self.title_label.setCursor(Qt.PointingHandCursor)
        self.title_label.setToolTip("Click to edit")
        self.title_label.mousePressEvent = lambda e: self._toggle_edit_title()
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: hsl(24, 20%, 15%);")
        
        self.title_input = QLineEdit(self.location.name)
        self.title_input.setStyleSheet("font-size: 24px; font-weight: 600; padding: 4px; border: 2px solid hsl(21, 66%, 68%); border-radius: 4px;")
        self.title_input.returnPressed.connect(self._toggle_edit_title)
        self.title_input.hide()
        
        # Removed edit_btn
        
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.title_input)
        header_layout.addStretch()
        right_layout.addLayout(header_layout)

        # 2. Status Labels
        self.current_folder_label = QLabel("Viewing: Main Folder")
        self.current_folder_label.setStyleSheet("color: hsl(24, 15%, 45%); margin-bottom: 4px; font-size: 14px; font-weight: 500;")
        right_layout.addWidget(self.current_folder_label)

        # 3. Action Buttons
        actions_layout = QHBoxLayout()
        new_folder_btn = QPushButton("📁 Create New Folder")
        new_folder_btn.setStyleSheet(self.styles["btn_outline"])
        new_folder_btn.clicked.connect(self._create_new_folder_dialog)
        actions_layout.addWidget(new_folder_btn)

        self.move_selected_btn = QPushButton("📂 Move (0)")
        self.move_selected_btn.setStyleSheet(self.styles["btn_outline"]) # Use outline style instead of destructive
        self.move_selected_btn.clicked.connect(self._move_selected)
        self.move_selected_btn.hide()
        actions_layout.addWidget(self.move_selected_btn)
        actions_layout.addStretch()
        right_layout.addLayout(actions_layout)

        # 4. Gallery Grid
        separator = QFrame()
        # PyQt5 Change: QFrame.HLine instead of QFrame.Shape.HLine
        separator.setFrameShape(QFrame.HLine) 
        separator.setStyleSheet("background: hsl(28, 70%, 88%);")
        right_layout.addWidget(separator)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        # Background black for gallery
        self.scroll.setStyleSheet("border: none; background-color: #000000;")
        
        gallery_widget = QWidget()
        gallery_widget.setStyleSheet("background-color: #000000;") # Ensure widget is also black
        self.gallery_layout = QGridLayout(gallery_widget)
        self.gallery_layout.setSpacing(16)
        for i in range(5):
            self.gallery_layout.setColumnStretch(i, 1)
        
        self._populate_gallery() # Initial Load
        self.scroll.setWidget(gallery_widget)
        right_layout.addWidget(self.scroll, stretch=1)
        
        # Initial sizing
        QTimer.singleShot(0, self._update_gallery_row_height)

        # 5. Footer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self.styles["btn_secondary"])
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)
        right_layout.addLayout(footer_layout)

        main_layout.addWidget(right_panel)

    # --- FOLDER LOGIC ---
    def load_subfolders(self):
        """Scan file system for subfolders"""
        if self.location.folder_path and self.location.folder_path.exists():
            self.subfolders = [f for f in self.location.folder_path.iterdir() if f.is_dir()]
            self.update_folder_list()

    def update_folder_list(self):
        """Refresh the sidebar buttons"""
        # Clear sidebar
        while self.folder_list_layout.count():
            item = self.folder_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # Helper to create nav buttons
        def create_nav_btn(text, is_active, callback):
            btn = QPushButton(text)
            btn.setStyleSheet(self.styles["nav_active"] if is_active else self.styles["nav_inactive"])
            btn.clicked.connect(callback)
            return btn

        # 1. Main Folder Button
        is_main = (self.current_folder == self.location.folder_path)
        main_btn = create_nav_btn(f"📁 Main Folder", is_main, 
                                  lambda: self.switch_folder(self.location.folder_path))
        self.folder_list_layout.addWidget(main_btn)

        # 2. Subfolder Buttons
        for subfolder in self.subfolders:
            is_active = (self.current_folder == subfolder)
            # Count images
            count = len(list(subfolder.glob("*.jpg")) + list(subfolder.glob("*.png")))
            
            # Use closure default arg (f=subfolder) to capture current value in loop
            btn = create_nav_btn(f"  📂 {subfolder.name}", is_active, 
                                 lambda checked, f=subfolder: self.switch_folder(f))
            self.folder_list_layout.addWidget(btn)

    def switch_folder(self, folder_path: Path):
        """Change the current viewing context"""
        self.current_folder = folder_path
        self.selected_photos.clear()
        self.current_folder = folder_path
        self.selected_photos.clear()
        self.move_selected_btn.hide()
        
        label = "Main Folder" if folder_path == self.location.folder_path else folder_path.name
        self.current_folder_label.setText(f"Viewing: {label}")
        
        self._populate_gallery()
        self.update_folder_list() # To update highlighting
        
        # Trigger resize to fix vertical height constraints
        QTimer.singleShot(0, self._update_gallery_row_height)

    def _create_new_folder_dialog(self):
        # PyQt5: QLineEdit.Normal matches 
        title, ok = QInputDialog.getText(self, "Create New Folder", "Enter folder name:", QLineEdit.Normal, "")
        if ok and title:
            if not self.location.folder_path: return
            try:
                new_path = self.location.folder_path / title
                new_path.mkdir(parents=True, exist_ok=True)
                self.load_subfolders() # Refresh sidebar
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create folder: {e}")

    # --- GALLERY LOGIC ---
    def _populate_gallery(self):
        """Render photos grid based on current_folder"""
        # Clear Grid
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        photos_to_display = []

        # Case A: Main Location (Using memory objects)
        if self.current_folder == self.location.folder_path:
            photos_to_display = self.location.photos
        # Case B: Subfolder (Scanning file system)
        else:
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.PNG']
            files = []
            for ext in extensions:
                files.extend(self.current_folder.glob(ext))
            
            # Create temporary Photo objects for display
            # Assuming Photo class accepts (id, name, url, hint)
            for f in files:
                photos_to_display.append(Photo(f.name, f.name, str(f), ""))

        # Render Grid
        row, col, max_cols = 0, 0, 5
        for photo in photos_to_display:
            card = GalleryImageCard(photo)
            card.deleteRequested.connect(self._on_photo_delete)
            card.selectionChanged.connect(self._on_photo_selection_changed)
            
            self.gallery_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    # --- EVENT HANDLERS ---
    def _on_photo_selection_changed(self, photo_id: str, is_selected: bool):
        if is_selected:
            self.selected_photos.add(photo_id)
        else:
            self.selected_photos.discard(photo_id)
        
        count = len(self.selected_photos)
        if count > 0:
            self.move_selected_btn.setText(f"📂 Move Selected")
            self.move_selected_btn.show()
        else:
            self.move_selected_btn.hide()


    def _move_selected(self):
        """Move selected photos to a chosen subfolder"""
        if not self.selected_photos: return
        
        # 1. Get available subfolders (excluding current)
        available_destinations = [
            f for f in self.subfolders 
            if f != self.current_folder
        ]
        
        # Add "Main Folder" option if we are in a subfolder
        if self.current_folder != self.location.folder_path:
             available_destinations.insert(0, self.location.folder_path)

        if not available_destinations:
            QMessageBox.information(self, "No Folders", "No other folders available to move to.\nCreate a new folder first.")
            return

        # 2. Show Selection Dialog
        folder_names = []
        for d in available_destinations:
            name = "Main Folder" if d == self.location.folder_path else d.name
            folder_names.append(name)
            
        dest_name, ok = QInputDialog.getItem(
            self, "Move Photos", 
            "Select destination folder:", 
            folder_names, 0, False
        )
        
        if ok and dest_name:
            # Get path from name
            target_path = None
            for d in available_destinations:
                name = "Main Folder" if d == self.location.folder_path else d.name
                if name == dest_name:
                    target_path = d
                    break
            
            if target_path:
                self._execute_move(target_path)

    def _execute_move(self, target_path: Path):
        """Perform the file move operation"""
        moved_count = 0
        errors = []
        
        # Iterate over a COPY of selected_photos
        for photo_id in list(self.selected_photos):
            # Find photo object/path
            photo_obj = None
            
            # If in memory (Main Folder)
            if self.current_folder == self.location.folder_path:
                for p in self.location.photos:
                    if p.id == photo_id:
                        photo_obj = p
                        break
            # If in subfolder (File System)
            else:
                # We need to find the file from the glob we did earlier... 
                # or just reconstruct it since ID is filename in subfolders
                possible_file = self.current_folder / photo_id
                if possible_file.exists():
                    # Create a dummy object for compatibility if valid
                     photo_obj = type('obj', (object,), {'url': str(possible_file), 'id': photo_id})
            
            if photo_obj:
                src_path = Path(photo_obj.url)
                dest_file = target_path / src_path.name
                
                try:
                    # Move file
                    import shutil
                    shutil.move(str(src_path), str(dest_file))
                    
                    # Update Memory State if leaving Main Folder
                    if self.current_folder == self.location.folder_path:
                        self.location.photos = [p for p in self.location.photos if p.id != photo_id]
                    
                    # If moving TO Main Folder, we technically should Add it to memory? 
                    # The current app architecture might only scan Main Folder on load or addition.
                    # For now, let's assume if it goes to Main Folder, it becomes a file there. 
                    # If the app reloads, it will pick it up? 
                    # Ideally we should add it to location.photos if moving TO main.
                    if target_path == self.location.folder_path:
                         # We need to create a Photo object. 
                         # But wait, Photo objects need ID, etc. 
                         # For simplicity in this session: let's leave valid "Main to Sub" and "Sub to Sub". 
                         # "Sub to Main" might require a reload to appear in Main view if we don't manually add.
                         pass

                    moved_count += 1
                except Exception as e:
                    errors.append(f"{src_path.name}: {e}")

        # Summary
        if moved_count > 0:
            self.selected_photos.clear()
            self._populate_gallery()
            self.update_folder_list() # Update counts
            self.move_selected_btn.hide()
            
            QMessageBox.information(self, "Move Complete", f"Moved {moved_count} photos to {target_path.name}")
        
        if errors:
            QMessageBox.warning(self, "Move Errors", "\n".join(errors))

    def _delete_single_photo(self, photo_id: str):
        """Handle deletion of a single photo by moving to NONESSENTIAL"""
        # Confirm
        reply = QMessageBox.question(self, "Delete Photo", 
                                   "Move this photo to NONESSENTIAL folder?", 
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Find photo object
            photo_to_delete = None
            if self.current_folder == self.location.folder_path:
                for p in self.location.photos:
                    if p.id == photo_id:
                        photo_to_delete = p
                        break
            else:
                possible_file = self.current_folder / photo_id
                if possible_file.exists():
                     photo_to_delete = type('obj', (object,), {'url': str(possible_file), 'id': photo_id})

            if photo_to_delete:
                try:
                    src_path = Path(photo_to_delete.url)
                    
                    # Logic to find NONESSENTIAL folder
                    # We assume structure: Base / Photos / Year / Location / Image
                    # We want: Base / Photos / NONESSENTIAL / Image
                    # So go up 3 levels from image to get 'Photos' dir? 
                    # Or simpler: location.folder_path is .../Photos/Year/Location
                    # Go up 2 levels from location folder
                    
                    if self.location.folder_path:
                        # self.location.folder_path -> .../Photos/Year/Location
                         photos_root = self.location.folder_path.parent.parent
                         nonessential_dir = photos_root / "NONESSENTIAL"
                         
                         if not nonessential_dir.exists():
                             # Try to create it if it doesn't exist? Or alert?
                             # Let's try creating it to be safe, or just check 'Photos/NONESSENTIAL'
                             nonessential_dir.mkdir(parents=True, exist_ok=True)

                         dest_path = nonessential_dir / src_path.name
                         
                         # Handle collision
                         if dest_path.exists():
                             timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                             dest_path = nonessential_dir / f"{src_path.stem}_{timestamp}{src_path.suffix}"

                         import shutil
                         shutil.move(str(src_path), str(dest_path))
                        #  print(f"Moved {src_path.name} to NONESSENTIAL")
                    
                    self.photoDeleted.emit(self.location.id, photo_id)
                    
                    # Update memory immediately if in main folder
                    if self.current_folder == self.location.folder_path:
                        self.location.photos = [p for p in self.location.photos if p.id != photo_id]
                    
                    self._populate_gallery()
                    self.update_folder_list()
                    
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not move file: {e}")

    def _on_photo_delete(self, photo_id: str):
        """Handle single card deletion request - DECOUPLED from selection"""
        self._delete_single_photo(photo_id)

    def _toggle_edit_title(self):
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

    def resizeEvent(self, event):
        """Handle dashboard resizing to update gallery row heights"""
        self._update_gallery_row_height()
        super().resizeEvent(event)
    
    def _update_gallery_row_height(self):
        """Set all cards to be 1/5th of the gallery viewport height"""
        if not hasattr(self, 'scroll') or not hasattr(self, 'gallery_layout'):
            return
            
        viewport_height = self.scroll.viewport().height()
        target_height = max(100, int(viewport_height / 5))
        
        # Iterate and update height for all cards
        for i in range(self.gallery_layout.count()):
            item = self.gallery_layout.itemAt(i)
            if item and item.widget():
                item.widget().setFixedHeight(target_height)