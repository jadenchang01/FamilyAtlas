# ============================================================================
# DATA MODELS
# ============================================================================

class Photo:
    """Represents a single photo"""
    def __init__(self, id: str, name: str, url: str, hint: str = ""):
        self.id = id
        self.name = name
        self.url = url  # File path
        self.hint = hint
        

class LocationGroup:
    """Represents a location with associated photos"""
    def __init__(self, id: str, name: str, lat: float, lng: float, year: str):
        self.id = id
        self.name = name
        self.lat = lat
        self.lng = lng
        self.year = year
        self.photos: List[Photo] = []
        self.folder_path: Optional[Path] = None