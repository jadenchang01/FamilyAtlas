from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

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