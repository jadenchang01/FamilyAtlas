from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# ============================================================================
# MAP BRIDGE - Python <-> JavaScript Communication
# ============================================================================

class MapBridge(QObject):
    """Python-JavaScript communication bridge"""
    
    coordinates_clicked = pyqtSignal(float, float)
    pin_clicked = pyqtSignal(str)
    
    @pyqtSlot(float, float)
    def on_map_click(self, lat: float, lng: float):
        """Called from JavaScript when map is clicked"""
        # print(f"Map clicked: {lat}, {lng}")
        self.coordinates_clicked.emit(lat, lng)
    
    @pyqtSlot(str)
    def on_pin_click(self, pin_id: str):
        """Called from JavaScript when pin is clicked"""
        # print(f"Pin clicked: {pin_id}")
        self.pin_clicked.emit(pin_id)


# ============================================================================
# MAP WIDGET - QWebEngineView with Leaflet
# ============================================================================

class MapWidget(QWebEngineView):
    """Interactive map widget using Leaflet"""
    
    coordinatesClicked = pyqtSignal(float, float)
    pinSelected = pyqtSignal(str)
    mapReady = pyqtSignal()  # NEW: Signal when map is ready
    
    def __init__(self):
        super().__init__()
        self.is_map_ready = False  # NEW: Track if map is loaded
        self.pending_pins = []     # NEW: Queue pins until map is ready
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
        
        # NEW: Wait for page to finish loading
        self.loadFinished.connect(self._on_load_finished)
    
    def _on_load_finished(self, success):
        """Called when page finishes loading"""
        if success:
            # Wait a bit more for JavaScript initialization
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(500, self._mark_map_ready)
    
    def _mark_map_ready(self):
        """Mark map as ready and add pending pins"""
        self.is_map_ready = True
        # print(f"✓ Map ready. Adding {len(self.pending_pins)} pending pins...")
        
        # Add all pending pins
        for pin_data in self.pending_pins:
            self._add_pin_now(*pin_data)
        
        self.pending_pins.clear()
        self.mapReady.emit()
    
    def add_pin(self, pin_id: str, lat: float, lng: float, title: str, photo_count: int = 0):
        """Add pin to map from Python"""
        if self.is_map_ready:
            # Map is ready, add immediately
            self._add_pin_now(pin_id, lat, lng, title, photo_count)
        else:
            # Map not ready yet, queue for later
            self.pending_pins.append((pin_id, lat, lng, title, photo_count))
    
    def _add_pin_now(self, pin_id: str, lat: float, lng: float, title: str, photo_count: int = 0):
        """Actually add pin to map (internal use only)"""
        # Escape single quotes in title to prevent JS errors
        title_escaped = title.replace("'", "\\'")
        js = f"addPin('{pin_id}', {lat}, {lng}, '{title_escaped}', {photo_count});"
        self.page().runJavaScript(js)
    
    def remove_pin(self, pin_id: str):
        """Remove pin from map"""
        if self.is_map_ready:
            js = f"removePin('{pin_id}');"
            self.page().runJavaScript(js)

    def clear_pins(self):
        """Remove all pins from map"""
        if self.is_map_ready:
            self.page().runJavaScript("clearPins();")
    
    def update_pin_count(self, pin_id: str, count: int):
        """Update photo count for pin"""
        if self.is_map_ready:
            js = f"updatePinCount('{pin_id}', {count});"
            self.page().runJavaScript(js)
    
    def center_map(self, lat: float, lng: float, zoom: int = 10):
        """Center map on coordinates"""
        if self.is_map_ready:
            js = f"map.setView([{lat}, {lng}], {zoom});"
            self.page().runJavaScript(js)
    
    def _generate_map_html(self) -> str:
        """Generate HTML with Leaflet map"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body { 
            margin: 0; 
            padding: 0; 
            background: hsl(28, 80%, 96%);
            /* Prevent touch gestures from propagating to body scale */
            touch-action: pan-x pan-y;
        }
        #map { 
            height: 100vh; 
            width: 100vw; 
        }
        .custom-popup {
            font-family: -apple-system, "Segoe UI", sans-serif;
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
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Store markers
        var markers = {};
        
        // Helper to get color scale
        function getPinColor(count) {
            // 1. Low: Bright Amber (High visibility against grey/blue maps)
            if (count < 10) return 'hsl(45, 100%, 55%)';   
            // 2. Med-Low: Safety Orange (The classic "warning" pop)
            if (count < 50) return 'hsl(30, 100%, 50%)';   
            // 3. Medium: Vivid Vermilion (Red-Orange)
            if (count < 100) return 'hsl(15, 100%, 50%)';  
            // 4. Med-High: Electric Red (Pure red, very striking)
            if (count < 200) return 'hsl(0, 95%, 45%)';    
            // 5. High: Deep Burgundy (Dark, intense, implies "density")
            return 'hsl(330, 100%, 30%)';                  
        }
        
        // Initialize Qt WebChannel
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            
            // Handle map clicks
            map.on('click', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                bridge.on_map_click(lat, lng);
            });
            
            console.log('Map initialized and ready');
        });
        
        // Add pin function (called from Python)
        function addPin(pinId, lat, lng, title, photoCount) {
            console.log('Adding pin:', pinId, lat, lng, title, photoCount);
            
            // Remove existing marker if present
            if (markers[pinId]) {
                map.removeLayer(markers[pinId]);
            }
            
            var color = getPinColor(photoCount);
            
            // Dynamic icon based on color
            var customIcon = L.divIcon({
                className: 'custom-marker',
                html: '<div style="background: ' + color + '; width: 22px; height: 22px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                iconSize: [22, 22],
                iconAnchor: [11, 11]
            });
            
            var marker = L.marker([lat, lng], {icon: customIcon}).addTo(map);
            
            var popupContent = '<div class="custom-popup"><div class="location-name">' + 
                              title + '</div><div class="photo-count">' + 
                              photoCount + ' photos</div></div>';
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
        
        function clearPins() {
            for (var id in markers) {
                if (markers.hasOwnProperty(id)) {
                    map.removeLayer(markers[id]);
                }
            }
            markers = {};
        }
        
        function updatePinCount(pinId, count) {
            if (markers[pinId]) {
                var color = getPinColor(count);
                
                // Update Icon color
                var newIcon = L.divIcon({
                    className: 'custom-marker',
                    html: '<div style="background: ' + color + '; width: 22px; height: 22px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                    iconSize: [22, 22],
                    iconAnchor: [11, 11]
                });
                markers[pinId].setIcon(newIcon);

                var popup = markers[pinId].getPopup();
                if (popup) {
                    var content = popup.getContent();
                    var titleMatch = content.match(/<div class="location-name">(.*?)<\\/div>/);
                    if (titleMatch) {
                        var title = titleMatch[1];
                        var popupContent = '<div class="custom-popup"><div class="location-name">' + 
                                          title + '</div><div class="photo-count">' + 
                                          count + ' photos</div></div>';
                        markers[pinId].setPopupContent(popupContent);
                    }
                }
            }
        }
    </script>
</body>
</html>
"""