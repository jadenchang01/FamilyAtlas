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
from models.data_models import LocationGroup

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

