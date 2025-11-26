#!/usr/bin/env python3
"""
Thermal Analyzer - Hot Spot Detection and Report Generation
Builds on SimpleFLIRProcessor to add intelligence layer for building surveys
"""

import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import json

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("PIL not installed. Install with: pip install Pillow")
    Image = ImageDraw = ImageFont = None


class HotSpot:
    """Represents a detected thermal anomaly"""
    
    def __init__(self, location: Tuple[int, int], temperature: float, 
                 area_size: int, severity: str):
        self.location = location  # (row, col) in temperature array
        self.temperature = temperature
        self.area_size = area_size  # number of pixels in hot spot
        self.severity = severity  # 'low', 'medium', 'high', 'critical'
        self.description = ""
        self.likely_cause = ""
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'location': self.location,
            'temperature': float(self.temperature),
            'area_size': int(self.area_size),
            'severity': self.severity,
            'description': self.description,
            'likely_cause': self.likely_cause
        }


class ThermalAnalyzer:
    """
    Advanced thermal analysis with hot spot detection and reporting
    
    This analyzer adds intelligence to SimpleFLIRProcessor:
    - Detects thermal anomalies (hot spots)
    - Labels and annotates images
    - Generates narrative reports for building surveys
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
        
        # Sensitivity multipliers for statistical detection
        self.sensitivity_map = {
            'low': 3.0,      # 3 std devs above mean
            'medium': 2.0,   # 2 std devs above mean
            'high': 1.5      # 1.5 std devs above mean
        }
        
    def detect_hot_spots(self, temp_data: np.ndarray, 
                        method='statistical',
                        threshold=None) -> List[HotSpot]:
        """
        Detect hot spots in thermal image data
        
        Args:
            temp_data: 2D numpy array of temperature values
            method: 'statistical' (auto), 'absolute' (fixed temp), 'relative' (local)
            threshold: Optional override threshold
            
        Returns:
            List of detected HotSpot objects
        """
        
        valid_data = temp_data[np.isfinite(temp_data)]
        if len(valid_data) == 0:
            return []
        
        if method == 'statistical':
            return self._detect_statistical(temp_data, threshold)
        elif method == 'absolute':
            return self._detect_absolute(temp_data, threshold)
        elif method == 'relative':
            return self._detect_relative(temp_data)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _detect_statistical(self, temp_data: np.ndarray, 
                           threshold=None) -> List[HotSpot]:
        """Statistical hot spot detection using mean + std deviation"""
        valid_data = temp_data[np.isfinite(temp_data)]
        mean_temp = np.mean(valid_data)
        std_temp = np.std(valid_data)
        
        # Use sensitivity or custom threshold
        multiplier = threshold if threshold else self.sensitivity_map[self.sensitivity]
        hot_threshold = mean_temp + (multiplier * std_temp)
        
        print(f"Detection: mean={mean_temp:.1f}°C, std={std_temp:.1f}°C")
        print(f"Hot spot threshold: {hot_threshold:.1f}°C")
        
        # Find pixels above threshold
        hot_mask = temp_data > hot_threshold
        
        return self._extract_hot_spots(temp_data, hot_mask, 'statistical')
    
    def _detect_absolute(self, temp_data: np.ndarray, 
                        threshold=None) -> List[HotSpot]:
        """Absolute temperature threshold detection"""
        thresh = threshold if threshold else self.base_threshold
        if thresh is None:
            thresh = 30.0  # Default 30°C
        
        print(f"Absolute threshold: {thresh}°C")
        hot_mask = temp_data > thresh
        
        return self._extract_hot_spots(temp_data, hot_mask, 'absolute')
    
    def _detect_relative(self, temp_data: np.ndarray) -> List[HotSpot]:
        """Local relative detection - finds local maxima"""
        # TODO: Implement local maxima detection
        # Uses scipy.ndimage to find local peaks
        print("Relative detection not yet implemented")
        return []
    
    def _extract_hot_spots(self, temp_data: np.ndarray, 
                          hot_mask: np.ndarray,
                          method_type: str) -> List[HotSpot]:
        """Extract connected components from hot spot mask"""
        from scipy import ndimage
        
        # Label connected regions
        labeled_array, num_features = ndimage.label(hot_mask)
        
        hot_spots = []
        
        for label in range(1, num_features + 1):
            # Get pixels for this hot spot
            region = labeled_array == label
            region_temps = temp_data[region]
            region_size = np.sum(region)
            
            # Skip very small regions (noise)
            if region_size < 3:
                continue
            
            # Find hottest point in region (centroid)
            max_temp = np.max(region_temps)
            max_loc = np.where((region) & (temp_data == max_temp))
            location = (int(max_loc[0][0]), int(max_loc[1][0]))
            
            # Determine severity
            severity = self._classify_severity(max_temp, temp_data)
            
            hot_spot = HotSpot(
                location=location,
                temperature=max_temp,
                area_size=int(region_size),
                severity=severity
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


# Example usage
if __name__ == "__main__":
    print("Thermal Analyzer Module")
    print("Import this module to use ThermalAnalyzer class")
