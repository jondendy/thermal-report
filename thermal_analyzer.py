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
    tects thermal anomalies (hot spots)
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
                """Local relative detection - finds local maxima (hot spots warmer than neighbors)"""
        from scipy.ndimage import maximum_filter
        
        # Use maximum filter to find local peaks
        # Each pixel is compared to neighborhood (e.g., 9x9 window)
        neighborhood_size = 9
        local_max = maximum_filter(temp_data, size=neighborhood_size)
        
        # A pixel is a local maximum if it equals the max in its neighborhood
        # and is significantly warmer than the mean
        valid_data = temp_data[np.isfinite(temp_data)]
        mean_temp = np.mean(valid_data)
        std_temp = np.std(valid_data)
        
        # Local peak must be warmer than local neighborhood AND above mean
        is_local_max = (temp_data == local_max) & (temp_data > mean_temp + std_temp)
        
        # Remove edges and create mask
        margin = neighborhood_size // 2
        is_local_max[:margin, :] = False
        is_local_max[-margin:, :] = False
        is_local_max[:, :margin] = False
        is_local_max[:, -margin:] = False
        
        print(f"Relative detection: found {np.sum(is_local_max)} local maxima")
        
        return self._extract_hot_spots(temp_data, is_local_max, 'relative')
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

            def label_hot_spots(self, image_path: str, hot_spots: List[HotSpot], 
                        output_path: str = None) -> Image:
        """
        Create annotated thermal image with hot spot markers and labels
        
        Args:
            image_path: Path to original thermal image
            hot_spots: List of detected HotSpot objects
            output_path: Optional path to save labeled image
            
        Returns:
            PIL Image with annotations
        """
        if Image is None:
            raise ImportError("PIL not available for image labeling")
        
        # Load image
        img = Image.open(image_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = font
        
        # Color map for severity
        severity_colors = {
            'low': '#FFFF00',      # Yellow
            'medium': '#FFA500',   # Orange
            'high': '#FF4500',     # Orange-Red
            'critical': '#FF0000'  # Red
        }
        
        # Label each hot spot
        for idx, spot in enumerate(hot_spots, 1):
            row, col = spot.location
            color = severity_colors.get(spot.severity, '#FF0000')
            
            # Draw crosshair marker
            marker_size = 10
            draw.line([(col-marker_size, row), (col+marker_size, row)], 
                     fill=color, width=2)
            draw.line([(col, row-marker_size), (col, row+marker_size)], 
                     fill=color, width=2)
            
            # Draw circle around hot spot
            radius = int(np.sqrt(spot.area_size) * 2)
            draw.ellipse([(col-radius, row-radius), (col+radius, row+radius)],
                        outline=color, width=2)
            
            # Add temperature label
            label = f"#{idx}: {spot.temperature:.1f}°C"
            # Position label above spot
            label_pos = (col + 15, row - 10)
            
            # Draw background for text
            bbox = draw.textbbox(label_pos, label, font=font)
            draw.rectangle(bbox, fill='black')
            draw.text(label_pos, label, fill=color, font=font)
            
            # Add severity indicator
            severity_label = f"[{spot.severity.upper()}]"
            severity_pos = (col + 15, row + 5)
            draw.text(severity_pos, severity_label, fill=color, font=small_font)
        
        # Add summary box
        summary_text = f"Hot Spots Detected: {len(hot_spots)}"
        summary_pos = (10, 10)
        summary_bbox = draw.textbbox(summary_pos, summary_text, font=font)
        draw.rectangle([(5, 5), (summary_bbox[2]+5, summary_bbox[3]+5)], 
                      fill='black', outline='white', width=2)
        draw.text(summary_pos, summary_text, fill='white', font=font)
        
        # Save if output path provided
        if output_path:
            img.save(output_path)
            print(f"Labeled image saved to: {output_path}")
        
        return img
    
    def assess_hot_spot_cause(self, hot_spot: HotSpot, 
                              image_context: Dict = None) -> str:
        """
        Interpret what the hot spot likely indicates for building surveys
        
        Args:
            hot_spot: HotSpot object to assess
            image_context: Optional context (location in building, etc.)
            
        Returns:
            String describing likely cause
        """
        causes = []
        
        # Assess based on severity
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
        
        else:  # low
            causes.append("Minor temperature variation")
            causes.append("Likely within normal building thermal patterns")
        
        # Add context-based assessment
        if image_context:
            location = image_context.get('location', '').lower()
            if 'wall' in location:
                causes.append("Wall location: check for stud thermal bridging or cavity issues")
            elif 'ceiling' in location:
                causes.append("Ceiling location: inspect attic insulation above this area")
            elif 'window' in location or 'door' in location:
                causes.append("Opening location: verify weather sealing and frame insulation")
        
        return ". ".join(causes) + "."
    
    def generate_report(self, image_name: str, hot_spots: List[HotSpot],
                       stats: Dict, image_context: Dict = None) -> str:
        """
        Generate narrative HTML report describing thermal findings
        
        Args:
            image_name: Name of thermal image
            hot_spots: List of detected hot spots
            stats: Dictionary with temperature statistics
            image_context: Optional context information
            
        Returns:
            HTML formatted report string
        """
        
        # Sort hot spots by severity and temperature
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_spots = sorted(hot_spots, 
                            key=lambda x: (severity_order[x.severity], -x.temperature))
        
        # Build HTML report
        html = []
        html.append('<div class="thermal-report">')
        html.append(f'<h2>Thermal Analysis Report: {image_name}</h2>')
        html.append(f'<p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
        
        # Executive Summary
        html.append('<div class="summary">')
        html.append('<h3>Executive Summary</h3>')
        html.append(f'<p><strong>Total Hot Spots Detected:</strong> {len(hot_spots)}</p>')
        
        # Count by severity
        severity_counts = {}
        for spot in hot_spots:
            severity_counts[spot.severity] = severity_counts.get(spot.severity, 0) + 1
        
        html.append('<p><strong>Severity Breakdown:</strong></p>')
        html.append('<ul>')
        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                html.append(f'<li class="{severity}">{severity.capitalize()}: {count}</li>')
        html.append('</ul>')
        
        # Temperature statistics
        html.append(f'<p><strong>Temperature Range:</strong> {stats.get("min_temp", 0):.1f}°C to {stats.get("max_temp", 0):.1f}°C</p>')
        html.append(f'<p><strong>Mean Temperature:</strong> {stats.get("mean_temp", 0):.1f}°C (±{stats.get("std_temp", 0):.1f}°C)</p>')
        html.append('</div>')
        
        # Detailed Findings
        if sorted_spots:
            html.append('<div class="findings">')
            html.append('<h3>Detailed Findings</h3>')
            
            for idx, spot in enumerate(sorted_spots, 1):
                html.append(f'<div class="hot-spot {spot.severity}">')
                html.append(f'<h4>Hot Spot #{idx} - {spot.severity.upper()} Priority</h4>')
                html.append(f'<p><strong>Location:</strong> Row {spot.location[0]}, Column {spot.location[1]}</p>')
                html.append(f'<p><strong>Temperature:</strong> {spot.temperature:.2f}°C</p>')
                html.append(f'<p><strong>Affected Area:</strong> {spot.area_size} pixels</p>')
                
                # Add interpretation
                cause_assessment = self.assess_hot_spot_cause(spot, image_context)
                html.append(f'<p><strong>Assessment:</strong> {cause_assessment}</p>')
                
                # Recommendations based on severity
                html.append('<p><strong>Recommendation:</strong> ')
                if spot.severity == 'critical':
                    html.append('Immediate investigation required. This anomaly indicates a serious thermal issue that should be addressed urgently.')
                elif spot.severity == 'high':
                    html.append('Priority investigation recommended. Schedule detailed inspection of this area.')
                elif spot.severity == 'medium':
                    html.append('Monitor this area. Consider investigation during routine maintenance.')
                else:
                    html.append('Document for reference. No immediate action required unless pattern persists.')
                html.append('</p>')
                
                html.append('</div>')
            
            html.append('</div>')
        
        # Recommendations section
        html.append('<div class="recommendations">')
        html.append('<h3>General Recommendations</h3>')
        html.append('<ul>')
        
        critical_count = severity_counts.get('critical', 0)
        high_count = severity_counts.get('high', 0)
        
        if critical_count > 0:
            html.append('<li><strong>URGENT:</strong> Address all critical hot spots immediately</li>')
            html.append('<li>Consider professional building inspection for critical areas</li>')
        
        if high_count > 0:
            html.append('<li>Schedule detailed inspection of high-priority hot spots within 2 weeks</li>')
        
        if len(hot_spots) > 5:
            html.append('<li>Multiple hot spots detected - consider comprehensive building envelope audit</li>')
        
        html.append('<li>Document conditions during survey (weather, time of day, HVAC status)</li>')
        html.append('<li>Consider follow-up thermal imaging after remediation</li>')
        html.append('<li>Verify findings with blower door test or moisture meter as appropriate</li>')
        html.append('</ul>')
        html.append('</div>')
        
        html.append('</div>')
        
        return '\n'.join(html)
    
    def detect_hot_spots_dual_method(self, temp_data: np.ndarray,
                                     relative_threshold: float = None,
                                     absolute_threshold: float = None) -> List[HotSpot]:
        """
        Primary: Relative detection with Backup: Fixed temperature detection
        User preference: "Relative temperature spots with a backup Fixed temperature overview"
        
        Args:
            temp_data: 2D numpy array of temperature values
            relative_threshold: Optional threshold for relative detection
            absolute_threshold: Optional threshold for absolute detection
            
        Returns:
            Combined list of hot spots from both methods
        """
        print("\n=== Dual Method Detection ===")
        print("PRIMARY: Relative (statistical) detection")
        print("BACKUP: Fixed temperature threshold detection")
        
        # Primary: Relative/Statistical detection
        primary_spots = self.detect_hot_spots(temp_data, method='statistical', 
                                              threshold=relative_threshold)
        
        # Backup: Absolute threshold detection
        backup_spots = self.detect_hot_spots(temp_data, method='absolute',
                                            threshold=absolute_threshold)
        
        # Merge results, removing duplicates
        # Two hot spots are duplicates if they're within 5 pixels of each other
        merged_spots = list(primary_spots)
        
        for backup_spot in backup_spots:
            is_duplicate = False
            for existing_spot in merged_spots:
                distance = np.sqrt(
                    (backup_spot.location[0] - existing_spot.location[0])**2 +
                    (backup_spot.location[1] - existing_spot.location[1])**2
                )
                if distance < 5:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                merged_spots.append(backup_spot)
        
        print(f"\nMerged Results: {len(merged_spots)} unique hot spots")
        print(f"  - From primary (relative): {len(primary_spots)}")
        print(f"  - From backup (absolute): {len(backup_spots)}")
        print(f"  - Additional from backup: {len(merged_spots) - len(primary_spots)}")
        
        return merged_spots


# Example usage
if __name__ == "__main__":
    print("Thermal Analyzer Module")
    print("Import this module to use ThermalAnalyzer class")
