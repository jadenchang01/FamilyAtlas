# ============================================================================
# DATA MODELS
# ============================================================================

from pathlib import Path
from typing import List, Optional


class Photo:
    """Represents a single photo"""
    def __init__(self, id: str, name: str, url: str, hint: str = ""):
        self.id = id
        self.name = name
        self.url = url
        self.hint = hint
    
    def to_dict(self) -> dict:
        """Convert Photo to dictionary for saving"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "hint": self.hint
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Photo':
        """Create Photo from dictionary"""
        return cls(
            id=data["id"],
            name=data["name"],
            url=data["url"],
            hint=data.get("hint", "")
        )
        

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
    
    def to_dict(self) -> dict:
        """Convert LocationGroup to dictionary for saving"""
        return {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "year": self.year,
            "folder_path": str(self.folder_path) if self.folder_path else None,
            "photos": [photo.to_dict() for photo in self.photos],
            "photo_count": len(self.photos)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LocationGroup':
        """Create LocationGroup from dictionary"""
        location = cls(
            id=data["id"],
            name=data["name"],
            lat=data["lat"],
            lng=data["lng"],
            year=data["year"]
        )
        
        if data.get("folder_path"):
            location.folder_path = Path(data["folder_path"])
        
        location.photos = [Photo.from_dict(p) for p in data.get("photos", [])]
        
        return location