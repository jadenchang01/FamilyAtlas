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
        header_layout = QHBoxLayout()
        self.title_label = QLabel(self.location.name)
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: hsl(24, 20%, 15%);")
        
        self.title_input = QLineEdit(self.location.name)
        self.title_input.setStyleSheet("font-size: 24px; font-weight: 600; padding: 4px; border: 2px solid hsl(21, 66%, 68%); border-radius: 4px;")
        self.title_input.hide()
        
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(32, 32)
        edit_btn.clicked.connect(self._toggle_edit_title)
        
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.title_input)
        header_layout.addWidget(edit_btn)
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

        self.delete_selected_btn = QPushButton("🗑️ Delete (0)")
        self.delete_selected_btn.setStyleSheet(self.styles["btn_destructive"])
        self.delete_selected_btn.clicked.connect(self._delete_selected)
        self.delete_selected_btn.hide()
        actions_layout.addWidget(self.delete_selected_btn)
        actions_layout.addStretch()
        right_layout.addLayout(actions_layout)

        # 4. Gallery Grid
        separator = QFrame()
        # PyQt5 Change: QFrame.HLine instead of QFrame.Shape.HLine
        separator.setFrameShape(QFrame.HLine) 
        separator.setStyleSheet("background: hsl(28, 70%, 88%);")
        right_layout.addWidget(separator)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(gallery_widget)
        self.gallery_layout.setSpacing(16)
        
        self._populate_gallery() # Initial Load
        scroll.setWidget(gallery_widget)
        right_layout.addWidget(scroll, stretch=1)

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
        main_btn = create_nav_btn(f"📁 Main Folder ({len(self.location.photos)})", is_main, 
                                  lambda: self.switch_folder(self.location.folder_path))
        self.folder_list_layout.addWidget(main_btn)

        # 2. Subfolder Buttons
        for subfolder in self.subfolders:
            is_active = (self.current_folder == subfolder)
            # Count images
            count = len(list(subfolder.glob("*.jpg")) + list(subfolder.glob("*.png")))
            
            # Use closure default arg (f=subfolder) to capture current value in loop
            btn = create_nav_btn(f"  📂 {subfolder.name} ({count})", is_active, 
                                 lambda checked, f=subfolder: self.switch_folder(f))
            self.folder_list_layout.addWidget(btn)

    def switch_folder(self, folder_path: Path):
        """Change the current viewing context"""
        self.current_folder = folder_path
        self.selected_photos.clear()
        self.delete_selected_btn.hide()
        
        label = "Main Folder" if folder_path == self.location.folder_path else folder_path.name
        self.current_folder_label.setText(f"Viewing: {label}")
        
        self._populate_gallery()
        self.update_folder_list() # To update highlighting

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
        row, col, max_cols = 0, 0, 3
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
            self.delete_selected_btn.setText(f"🗑️ Delete ({count})")
            self.delete_selected_btn.show()
        else:
            self.delete_selected_btn.hide()

    def _delete_selected(self):
        if not self.selected_photos: return
        
        # PyQt5 Change: QMessageBox.Yes (not StandardButton.Yes)
        reply = QMessageBox.question(self, "Delete Photos", 
                                   f"Delete {len(self.selected_photos)} photos?", 
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Create a copy of the set to iterate safely
            for pid in list(self.selected_photos):
                self.photoDeleted.emit(self.location.id, pid)
                
                # If in main folder, update memory immediately
                if self.current_folder == self.location.folder_path:
                     self.location.photos = [p for p in self.location.photos if p.id != pid]

            self.selected_photos.clear()
            self._populate_gallery()
            self.update_folder_list()

    def _on_photo_delete(self, photo_id: str):
        """Handle single card deletion request"""
        # Add to selection and trigger standard delete flow
        self.selected_photos.add(photo_id)
        self._delete_selected()

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