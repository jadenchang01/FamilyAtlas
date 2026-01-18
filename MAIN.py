import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Import all components
from models.data_models import Photo, LocationGroup
from workers.image_processing_thread import ImageProcessingThread
from widgets.map_widget import MapWidget
from widgets.gallery_image_card import GalleryImageCard
from widgets.location_dashboard import LocationDashboard
from widgets.sidebar import Sidebar
from windows.photo_map_organizer import PhotoMapOrganizer


def main():
    """Main application entry point"""
    
    # Create Qt Application
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Family Atlas")
    app.setOrganizationName("PhotoOrganizer")
    app.setApplicationVersion("1.0.0")
    
    # Set application-wide style
    app.setStyle("Fusion")
    
    # Optional: Set application-wide stylesheet for consistent theming
    app.setStyleSheet("""
        * {
            font-family: Helvetica Neue;
        }
    """)
    
    # Create and show main window
    window = PhotoMapOrganizer()
    window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()