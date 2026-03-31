from PIL import Image
from typing import List, Dict
import uuid

class MaskAnalyzer:
    """Analyzes projection masks to detect zones - simplified version without OpenCV"""
    
    def __init__(self):
        self.min_area_threshold = 100  # Minimum pixels for a valid zone
        self.width = 0
        self.height = 0
    
    def analyze_mask(self, filepath: str) -> List[Dict]:
        """
        Analyze a PNG mask and return detected zones
        White pixels (255, 255, 255) are projection areas
        Black pixels (0, 0, 0) are masked areas
        """
        # Load image
        with Image.open(filepath) as opened:
            img = opened.convert('RGB')
        self.width, self.height = img.size
        pixels = img.load()
        
        # Find bounding box of all white pixels
        min_x, min_y = self.width, self.height
        max_x, max_y = 0, 0
        has_white = False
        
        # Scan entire image to find white pixel bounds
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = pixels[x, y]
                # Check if pixel is white (allowing some tolerance)
                if r > 250 and g > 250 and b > 250:
                    has_white = True
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        
        zones = []
        
        if has_white:
            # Create a zone for the bounding box of white pixels
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            
            zone = {
                "id": str(uuid.uuid4()),
                "bounds": {
                    "x": min_x,
                    "y": min_y,
                    "width": width,
                    "height": height
                },
                "center": {
                    "x": min_x + width // 2,
                    "y": min_y + height // 2
                },
                "area": width * height,
                "aspectRatio": round(width / height, 2) if height > 0 else 1
            }
            zones.append(zone)
        else:
            # No white pixels found, use full image as fallback
            zones.append({
                "id": str(uuid.uuid4()),
                "bounds": {
                    "x": 0,
                    "y": 0,
                    "width": self.width,
                    "height": self.height
                },
                "center": {
                    "x": self.width // 2,
                    "y": self.height // 2
                },
                "area": self.width * self.height,
                "aspectRatio": round(self.width / self.height, 2) if self.height > 0 else 1
            })
        
        return zones
    
    def _find_zone_bounds(self, img, start_x, start_y, visited):
        """Simple bounding box finder around a white region"""
        pixels = img.load()
        
        # Find bounds by scanning outward
        min_x, max_x = start_x, start_x
        min_y, max_y = start_y, start_y
        
        # Scan in expanding rectangles
        for radius in range(10, min(self.width, self.height) // 2, 10):
            found_white = False
            
            # Top and bottom edges
            for x in range(max(0, start_x - radius), min(self.width, start_x + radius)):
                if start_y - radius >= 0:
                    r, g, b = pixels[x, start_y - radius]
                    if r == 255 and g == 255 and b == 255:
                        min_y = start_y - radius
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        found_white = True
                
                if start_y + radius < self.height:
                    r, g, b = pixels[x, start_y + radius]
                    if r == 255 and g == 255 and b == 255:
                        max_y = start_y + radius
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        found_white = True
            
            # Left and right edges
            for y in range(max(0, start_y - radius), min(self.height, start_y + radius)):
                if start_x - radius >= 0:
                    r, g, b = pixels[start_x - radius, y]
                    if r == 255 and g == 255 and b == 255:
                        min_x = start_x - radius
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)
                        found_white = True
                
                if start_x + radius < self.width:
                    r, g, b = pixels[start_x + radius, y]
                    if r == 255 and g == 255 and b == 255:
                        max_x = start_x + radius
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)
                        found_white = True
            
            if not found_white:
                break
        
        # Mark region as visited
        for y in range(min_y, max_y + 1, 10):
            for x in range(min_x, max_x + 1, 10):
                visited.add((x, y))
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width * height < self.min_area_threshold:
            return None
        
        return {
            "x": min_x,
            "y": min_y,
            "width": width,
            "height": height
        }
    
    def classify_zone_size(self, area: int) -> str:
        """
        Classify zone size based on area
        """
        total_area = self.width * self.height
        if total_area == 0:
            return "unknown"
        
        percentage = (area / total_area) * 100
        
        if percentage > 20:
            return "large"
        elif percentage > 5:
            return "medium"
        else:
            return "small"
