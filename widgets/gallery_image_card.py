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
from PyQt5.QtGui import QPixmap, QIcon, QImage, QPalette, QColor, QImageReader
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
        self.setMinimumSize(120, 90) # Allow shrinking
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Allow growing
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._update_style()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Image container
        image_container = QWidget()
        # image_container.setFixedSize(300, 225) # REMOVE FIXED SIZE
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setScaledContents(True)
        # self.image_label.setFixedSize(300, 225) # REMOVE FIXED SIZE
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored) # Allow full resizing
        
        # Load image with orientation support (EXIF)
        reader = QImageReader(self.photo.url)
        reader.setAutoTransform(True)
        image = reader.read()
        
        if not image.isNull():
             pixmap = QPixmap.fromImage(image)
             # Scale initially but rely on ScaledContents for resizing
             # We don't need to pre-scale perfectly here if ScaledContents is True
             self.image_label.setPixmap(pixmap)
        
        image_layout.addWidget(self.image_label)
        
        # Overlay widget (shown on hover)
        self.overlay = QWidget(self) # Parent to self, not container, to overlay easily
        self.overlay.setStyleSheet("background: rgba(0, 0, 0, 0.4);") # Darker overlay for better visibility
        # self.overlay.setFixedSize(300, 225) # REMOVE FIXED SIZE
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
        self.overlay.hide()
        
        layout.addWidget(image_container)

    def resizeEvent(self, event):
        """Handle resizing of the card"""
        self.overlay.resize(self.size())
        self.overlay.raise_()
        super().resizeEvent(event)
    
    def _update_style(self):
        """Update card border/background to reflect selected state"""
        if self.is_selected:
            self.setStyleSheet("""
                GalleryImageCard {
                    background: #2a2a2a;
                    border: 2px solid hsl(21, 66%, 68%);
                    border-radius: 8px;
                }
                GalleryImageCard:hover {
                    border: 2px solid hsl(21, 66%, 88%);
                    background: #333333;
                }
            """)
        else:
            self.setStyleSheet("""
                GalleryImageCard {
                    background: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 8px;
                }
                GalleryImageCard:hover {
                    border: 2px solid hsl(21, 66%, 68%);
                    background: #2a2a2a;
                }
            """)

    def _on_selection_changed(self, state):
        """Handle checkbox state change"""
        self.is_selected = (state == Qt.Checked)
        self._update_style()
        self.selectionChanged.emit(self.photo.id, self.is_selected)
    
    def enterEvent(self, event):
        """Show overlay on hover"""
        self.overlay.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide overlay only if not selected — keep visible to show checkbox state"""
        if not self.is_selected:
            self.overlay.hide()
        super().leaveEvent(event)