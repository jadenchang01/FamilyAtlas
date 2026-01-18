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
from models.data_models import Photo

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
        self.is_selected = (state == Qt.Checked)
        self.selectionChanged.emit(self.photo.id, self.is_selected)
    
    def enterEvent(self, event):
        """Show overlay on hover"""
        self.overlay.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide overlay when not hovering"""
        self.overlay.hide()
        super().leaveEvent(event)