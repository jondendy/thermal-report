#!/usr/bin/env python3
"""
Thermal Analyzer - Hot Spot Detection and Report Generation
Builds on SimpleFLIRProcessor to add intelligence layer for building surveys
"""
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
import json

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("PIL not installed. Install with: pip install Pillow")
    Image = ImageDraw = ImageFont = None


class HotSpot:
    """Represents a detected thermal anomaly"""
    
    def __init__(self, location: Tuple[int, int], temperature: float, area_size: int, severity: str, thermal_shape: Tuple[int, int] = None, image_shape: Tuple[int, int] = None):
        self.location = location
        self.temperature = temperature
        self.area_size = area_size
        self.severity = severity
        self.description = ""
        self.likely_cause = ""
        self.thermal_shape = thermal_shape
        self.image_shape = image_shape
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization with pixel coordinates"""
        row, col = self.location
        
        if self.thermal_shape and self.image_shape:
            scale_y = self.image_shape[0] / self.thermal_shape[0]
            scale_x = self.image_shape[1] / self.thermal_shape[1]
        else:
            scale_y = 4.0
            scale_x = 4.0
        
        x = int(col * scale_x)
        y = int(row * scale_y)
        
        return {
            'x': x,
            'y': y,
            'location': [x, y],
            'temperature': float(self.temperature),
            'area_size': int(self.area_size),
            'severity': self.severity,
            'description': self.description,
            'likely_cause': self.likely_cause
        }


class ThermalAnalyzer:
    """
    Advanced thermal analysis with hot spot detection and reporting
    """
    
    def __init__(self, base_temp_threshold=None, sensitivity='medium'):
        """
        Initialize thermal analyzer
        
        Args:
            base_temp_threshold: Base temperature for absolute detection (None for auto)
            sensitivity: 'low', 'medium', or 'high' - affects detection threshold
        """
        self.base_threshold = base_temp_threshold
        self.sensitivity = sensitivity
        
        self.sensitivity_map = {
            'low': 3.0,
            'medium': 2.0,
            'high': 1.5
        }
    
    def detect_hot_spots(
        self, 
        temp_data: np.ndarray, 
        method='statistical', 
        threshold=None, 
        image_path: str = None,
        max_spots: int = None
    ) -> List[HotSpot]:
        """
        Detect hot spots in thermal image data
        
        Args:
            temp_data: 2D numpy array of temperature values
            method: 'statistical' (auto), 'absolute' (fixed temp), 'relative' (local)
            threshold: Optional override threshold
            image_path: Optional path to image for getting visual dimensions
            max_spots: Maximum number of spots to return (keeps hottest)
        
        Returns:
            List of detected HotSpot objects, sorted by temperature if max_spots set
        """
        thermal_shape = temp_data.shape
        image_shape = None
        if image_path and Image:
            try:
                with Image.open(image_path) as img:
                    image_shape = (img.height, img.width)
            except:
                pass
        
        valid_mask = np.isfinite(temp_data) & (temp_data > -45.0)
        valid_data = temp_data[valid_mask]
        if len(valid_data) == 0:
            return []
        
        if method == 'statistical':
            hot_spots = self._detect_statistical(temp_data, threshold, thermal_shape, image_shape)
        elif method == 'absolute':
            hot_spots = self._detect_absolute(temp_data, threshold, thermal_shape, image_shape)
        elif method == 'relative':
            hot_spots = self._detect_relative(temp_data, thermal_shape, image_shape)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Apply max_spots cap if specified
        if max_spots and len(hot_spots) > max_spots:
            # Sort by temperature descending, keep top N
            hot_spots_sorted = sorted(hot_spots, key=lambda s: s.temperature, reverse=True)
            hot_spots = hot_spots_sorted[:max_spots]
            print(f"Capped to top {max_spots} hottest spots (from {len(hot_spots_sorted)})")
        
        return hot_spots
    
    def _detect_statistical(self, temp_data: np.ndarray, threshold=None, thermal_shape=None, image_shape=None) -> List[HotSpot]:
        """Statistical hot spot detection using mean + std deviation"""
        valid_data = temp_data[np.isfinite(temp_data)]
        mean_temp = np.mean(valid_data)
        std_temp = np.std(valid_data)
        
        multiplier = threshold if threshold else self.sensitivity_map[self.sensitivity]
        hot_threshold = mean_temp + (multiplier * std_temp)
        
        print(f"Detection: mean={mean_temp:.1f}°C, std={std_temp:.1f}°C, sensitivity={self.sensitivity}")
        print(f"Hot spot threshold: {hot_threshold:.1f}°C ({multiplier}σ)")
        
        hot_mask = temp_data > hot_threshold
        
        return self._extract_hot_spots(temp_data, hot_mask, 'statistical', thermal_shape, image_shape)
    
    def _detect_absolute(self, temp_data: np.ndarray, threshold=None, thermal_shape=None, image_shape=None) -> List[HotSpot]:
        """Absolute temperature threshold detection"""
        thresh = threshold if threshold else self.base_threshold
        if thresh is None:
            thresh = 30.0
        
        print(f"Absolute threshold: {thresh}°C")
        hot_mask = temp_data > thresh
        
        return self._extract_hot_spots(temp_data, hot_mask, 'absolute', thermal_shape, image_shape)
    
    def _detect_relative(self, temp_data: np.ndarray, thermal_shape=None, image_shape=None) -> List[HotSpot]:
        """Local relative detection - finds local maxima"""
        from scipy.ndimage import maximum_filter
        
        neighborhood_size = 9
        local_max = maximum_filter(temp_data, size=neighborhood_size)
        
        valid_data = temp_data[np.isfinite(temp_data)]
        mean_temp = np.mean(valid_data)
        std_temp = np.std(valid_data)
        
        is_local_max = (temp_data == local_max) & (temp_data > mean_temp + std_temp)
        
        margin = neighborhood_size // 2
        is_local_max[:margin, :] = False
        is_local_max[-margin:, :] = False
        is_local_max[:, :margin] = False
        is_local_max[:, -margin:] = False
        
        print(f"Relative detection: found {np.sum(is_local_max)} local maxima")
        
        return self._extract_hot_spots(temp_data, is_local_max, 'relative', thermal_shape, image_shape)
    
    def _extract_hot_spots(self, temp_data: np.ndarray, hot_mask: np.ndarray, method_type: str, thermal_shape=None, image_shape=None) -> List[HotSpot]:
        """Extract connected components from hot spot mask"""
        from scipy import ndimage
        
        labeled_array, num_features = ndimage.label(hot_mask)
        
        hot_spots = []
        
        for label in range(1, num_features + 1):
            region = labeled_array == label
            region_temps = temp_data[region]
            region_size = np.sum(region)
            
            if region_size < 3:
                continue
            
            max_temp = np.max(region_temps)
            max_loc = np.where((region) & (temp_data == max_temp))
            location = (int(max_loc[0][0]), int(max_loc[1][0]))
            
            severity = self._classify_severity(max_temp, temp_data)
            
            hot_spot = HotSpot(
                location=location,
                temperature=max_temp,
                area_size=int(region_size),
                severity=severity,
                thermal_shape=thermal_shape or temp_data.shape,
                image_shape=image_shape
            )
            
            hot_spots.append(hot_spot)
        
        print(f"Found {len(hot_spots)} hot spots using {method_type} method")
        return hot_spots
    
    def _classify_severity(self, temp: float, temp_data: np.ndarray) -> str:
        """Classify hot spot severity based on temperature"""
        valid_data = temp_data[np.isfinite(temp_data)]
        mean = np.mean(valid_data)
        std = np.std(valid_data)
        
        delta = temp - mean
        
        if delta > 3 * std:
            return 'critical'
        elif delta > 2 * std:
            return 'high'
        elif delta > std:
            return 'medium'
        else:
            return 'low'
    
    def label_hot_spots(self, image_path: str, hot_spots: List[HotSpot], output_path: str = None) -> Image:
        """Create annotated thermal image with hot spot markers and labels"""
        if Image is None:
            raise ImportError("PIL not available for image labeling")
        
        img = Image.open(image_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = font
        
        severity_colors = {
            'low': '#FFFF00',
            'medium': '#FFA500',
            'high': '#FF4500',
            'critical': '#FF0000'
        }
        
        for idx, spot in enumerate(hot_spots, 1):
            spot_dict = spot.to_dict()
            col = spot_dict['x']
            row = spot_dict['y']
            color = severity_colors.get(spot.severity, '#FF0000')
            
            marker_size = 10
            draw.line([(col-marker_size, row), (col+marker_size, row)], fill=color, width=2)
            draw.line([(col, row-marker_size), (col, row+marker_size)], fill=color, width=2)
            
            radius = int(np.sqrt(spot.area_size) * 2)
            draw.ellipse([(col-radius, row-radius), (col+radius, row+radius)], outline=color, width=2)
            
            label = f"#{idx}: {spot.temperature:.1f}°C"
            label_pos = (col + 15, row - 10)
            
            bbox = draw.textbbox(label_pos, label, font=font)
            draw.rectangle(bbox, fill='black')
            draw.text(label_pos, label, fill=color, font=font)
            
            severity_label = f"[{spot.severity.upper()}]"
            severity_pos = (col + 15, row + 5)
            draw.text(severity_pos, severity_label, fill=color, font=small_font)
        
        summary_text = f"Hot Spots Detected: {len(hot_spots)}"
        summary_pos = (10, 10)
        summary_bbox = draw.textbbox(summary_pos, summary_text, font=font)
        draw.rectangle([(5, 5), (summary_bbox[2]+5, summary_bbox[3]+5)], fill='black', outline='white', width=2)
        draw.text(summary_pos, summary_text, fill='white', font=font)
        
        if output_path:
            img.save(output_path)
            print(f"Labeled image saved to: {output_path}")
        
        return img
    
    def assess_hot_spot_cause(self, hot_spot: HotSpot, image_context: Dict = None) -> str:
        """Interpret what the hot spot likely indicates for building surveys"""
        causes = []
        
        if hot_spot.severity == 'critical':
            causes.append("Significant thermal anomaly detected")
            if hot_spot.area_size > 100:
                causes.append("Large area suggests major insulation failure or active heat source")
            else:
                causes.append("Localized hot spot may indicate electrical issue or severe air leak")
        elif hot_spot.severity == 'high':
            causes.append("Notable temperature elevation")
            if hot_spot.area_size > 50:
                causes.append("Possible insulation gap or thermal bridging")
            else:
                causes.append("May indicate air infiltration point or small heat source")
        elif hot_spot.severity == 'medium':
            causes.append("Moderate thermal anomaly")
            causes.append("Could be minor insulation issue or normal building variation")
        else:
            causes.append("Minor temperature variation")
            causes.append("Likely within normal building thermal patterns")
        
        if image_context:
            location = image_context.get('location', '').lower()
            if 'wall' in location:
                causes.append("Wall location: check for stud thermal bridging or cavity issues")
            elif 'ceiling' in location:
                causes.append("Ceiling location: inspect attic insulation above this area")
            elif 'window' in location or 'door' in location:
                causes.append("Opening location: verify weather sealing and frame insulation")
        
        return ". ".join(causes) + "."
    
    def generate_report(self, image_name: str, hot_spots: List[HotSpot], stats: Dict, image_context: Dict = None) -> str:
        """Generate narrative HTML report describing thermal findings"""
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_spots = sorted(hot_spots, key=lambda x: (severity_order[x.severity], -x.temperature))
        
        html = []
        html.append('<div class="thermal-report">')
        html.append(f'<h2>Thermal Analysis Report: {image_name}</h2>')
        html.append(f'<p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
        html.append('<div class="summary">')
        html.append('<h3>Executive Summary</h3>')
        html.append(f'<p><strong>Total Hot Spots Detected:</strong> {len(hot_spots)}</p>')
        
        severity_counts = {}
        for spot in hot_spots:
            severity_counts[spot.severity] = severity_counts.get(spot.severity, 0) + 1

        return '\n'.join(html)

    def merge_labels_with_analysis(self, analysis: Dict[str, Any], labels: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Merge thermal analysis hot spots with operator labels"""
        findings = []
        labeled_spots = labels.get('labeled_spots', [])
        
        for labeled in labeled_spots:
            findings.append({
                'image_name': labeled.get('image_name'),
                'spot_number': labeled.get('spot_number'),
                'type': labeled.get('type'),
                'temperature': labeled.get('temperature'),
                'severity': labeled.get('severity', 'medium'),
                'location': labeled.get('location', [0, 0]),
                'description': f"{labeled.get('type')} heat loss detected"
            })
        
        return findings
