#!/usr/bin/env python3
"""
Heat Loss Reporter - Professional thermal survey report generation
Focuses on heat loss assessment and energy-saving recommendations
"""

import json
import base64
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class HeatLossReporter:
    """
    Generate professional heat loss reports for building thermal surveys.
    
    Takes labeled hot spots from thermal images and creates comprehensive
    reports with energy-saving recommendations.
    """
    
    def __init__(self, org_name: str = "", org_website: str = "", org_contact: str = "", recommendations_file: Optional[Path] = None):
        """
        Initialize reporter with energy-saving recommendations database.
        
        Args:
            org_name: Organization name for report
            org_website: Organization website
            org_contact: Organization contact info
            recommendations_file: Path to JSON file with recommendations by type
        """
        self.org_name = org_name
        self.org_website = org_website
        self.org_contact = org_contact
        self.recommendations_file = recommendations_file
        self.recommendations = self._load_recommendations()
    
    def _load_recommendations(self) -> Dict:
        """Load energy-saving recommendations from JSON file"""
        if self.recommendations_file and Path(self.recommendations_file).exists():
            with open(self.recommendations_file, 'r') as f:
                return json.load(f)
        else:
            # Fallback defaults
            return self._get_default_recommendations()
    
    def _get_default_recommendations(self) -> Dict:
        """Provide default recommendations if file not found"""
        return {
            "Window": {
                "advice": [
                    "Install thermal curtains or cellular shades",
                    "Add weather stripping around frame",
                    "Consider secondary glazing or window film",
                    "Check for gaps and seal with appropriate caulk"
                ],
                "savings": "10-20% on heating costs",
                "priority": "high"
            },
            "Door": {
                "advice": [
                    "Install or replace door sweep at bottom",
                    "Add weather stripping to frame",
                    "Consider thermal door curtain",
                    "Check threshold and seal gaps"
                ],
                "savings": "5-10% on heating costs",
                "priority": "medium"
            },
            "Wall": {
                "advice": [
                    "Inspect cavity insulation levels",
                    "Consider external or internal wall insulation",
                    "Check for thermal bridging at structural elements",
                    "Investigate damp or missing insulation"
                ],
                "savings": "15-35% on heating costs",
                "priority": "high"
            },
            "Eaves": {
                "advice": [
                    "Improve loft insulation to 270mm depth",
                    "Seal gaps between wall and roof",
                    "Check for ventilation/insulation balance",
                    "Install eaves insulation baffles"
                ],
                "savings": "20-30% on heating costs",
                "priority": "high"
            },
            "Vent": {
                "advice": [
                    "Install controllable trickle vents",
                    "Check if vent is necessary or can be sealed",
                    "Consider heat recovery ventilation",
                    "Ensure vent serves its intended purpose"
                ],
                "savings": "5-10% on heating costs",
                "priority": "low"
            },
            "Roof": {
                "advice": [
                    "Increase loft insulation depth",
                    "Check for gaps or compressed insulation",
                    "Inspect roof tiles for damage",
                    "Consider warm roof construction for flat roofs"
                ],
                "savings": "25-35% on heating costs",
                "priority": "high"
            },
            "Chimney": {
                "advice": [
                    "Install chimney balloon or cap when not in use",
                    "Consider chimney sheep draught excluder",
                    "Seal around fireplace opening",
                    "Check flue damper operation"
                ],
                "savings": "5-15% on heating costs",
                "priority": "medium"
            },
            "Porch": {
                "advice": [
                    "Create thermal air-lock with second door",
                    "Improve porch insulation",
                    "Seal gaps around door frames",
                    "Consider enclosed porch addition"
                ],
                "savings": "5-10% on heating costs",
                "priority": "medium"
            }
        }
    
    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """
        Encode image file to base64 string for embedding in HTML/PDF.
        
        This method reads an image file and converts it to a base64-encoded string
        that can be embedded directly in HTML using data URIs. This approach:
        - Avoids file path resolution issues in WeasyPrint
        - Ensures images are properly embedded in generated PDFs
        - Prevents the PDF bloat that occurs with certain file path formats
        
        Args:
            image_path: Path to image file (Path object or string)
            
        Returns:
            Base64-encoded string (without data URI prefix) or None if error
            
        Example usage:
            b64_data = self._encode_image_to_base64(Path("thermal.jpg"))
            html_img = f'<img src="data:image/jpeg;base64,{b64_data}">'
        """
        try:
            image_path = Path(image_path)  # Ensure it's a Path object
            
            if not image_path.exists():
                logging.warning(f"Image file not found: {image_path}")
                return None
            
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                img_data_b64 = base64.b64encode(img_data).decode('utf-8')
                return img_data_b64
                
        except Exception as e:
            logging.error(f"Failed to encode image {image_path}: {e}")
            return None
    
    def group_by_spot_number(self, labeled_spots: List[Dict]) -> Dict[int, List[Dict]]:
        """
        Group hot spots by their assigned number for cross-image reporting.
        
        Args:
            labeled_spots: List of labeled hot spot dictionaries
            
        Returns:
            Dictionary mapping spot number to list of occurrences
        """
        grouped = {}
        for spot in labeled_spots:
            spot_num = spot.get('spot_number')
            if spot_num not in grouped:
                grouped[spot_num] = []
            grouped[spot_num].append(spot)
        
        return grouped
    
    def generate_finding_narrative(self, spot_group: List[Dict], spot_number: int) -> Dict:
        """
        Generate narrative description for a numbered heat loss finding.
        
        Args:
            spot_group: List of hot spot occurrences with same number
            spot_number: The assigned spot number
            
        Returns:
            Dictionary with finding details
        """
        # Get common type (should be same for all in group)
        spot_type = spot_group[0].get('type', 'Unknown')
        
        # Calculate statistics
        temps = [spot.get('temperature', 0) for spot in spot_group if isinstance(spot.get('temperature'), (int, float))]
        max_temp = max(temps) if temps else 0
        min_temp = min(temps) if temps else 0
        avg_temp = sum(temps) / len(temps) if temps else 0
        
        # Get severity (use highest)
        severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        severities = [spot.get('severity', 'low') for spot in spot_group]
        max_severity = max(severities, key=lambda s: severity_order.get(s, 0))
        
        # Build description
        if len(spot_group) == 1:
            description = f"Heat loss detected at {spot_type.lower()} location."
        else:
            description = f"Heat loss detected at {spot_type.lower()} visible in {len(spot_group)} images."
        
        # Add temperature context
        if temps:
            description += f" Temperature readings range from {min_temp:.1f}°C to {max_temp:.1f}°C, "
            description += f"averaging {avg_temp:.1f}°C. "
        else:
            description += " Temperature readings were not available for this point. "
        
        # Add severity context
        if max_severity == 'critical':
            description += "This represents a critical heat loss point requiring immediate attention."
        elif max_severity == 'high':
            description += "This is a significant heat loss area that should be addressed promptly."
        elif max_severity == 'medium':
            description += "This represents moderate heat loss that should be addressed."
        else:
            description += "This is a minor heat loss point for consideration."
        
        # Get recommendations
        recommendations = self.recommendations.get(spot_type, {})
        
        return {
            'spot_number': spot_number,
            'type': spot_type,
            'title': f"Heat loss at {spot_type} #{spot_number}",
            'description': description,
            'max_temp': max_temp,
            'min_temp': min_temp,
            'avg_temp': avg_temp,
            'severity': max_severity,
            'image_count': len(spot_group),
            'images': [spot.get('image_name', '') for spot in spot_group],
            'recommendations': recommendations,
            'spot_locations': [(spot.get('image_name', ''), spot.get('location', [])) for spot in spot_group]
        }
    
    def generate_executive_summary(self, findings: List[Dict]) -> Dict:
        """
        Generate executive summary statistics.
        
        Args:
            findings: List of finding dictionaries
            
        Returns:
            Summary statistics dictionary
        """
        severity_order = ['low', 'medium', 'high', 'critical']
        severity_counts = {s: 0 for s in severity_order}
        
        for finding in findings:
            severity = finding.get('severity', 'low')
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Find highest severity
        highest_severity = 'low'
        for sev in reversed(severity_order):
            if severity_counts[sev] > 0:
                highest_severity = sev
                break
        
        return {
            'total_findings': len(findings),
            'highest_severity': highest_severity.capitalize(),
            'severity_breakdown': severity_counts,
            'critical_count': severity_counts.get('critical', 0),
            'high_count': severity_counts.get('high', 0)
        }
    
    def generate_recommendations(self, findings: List[Dict]) -> List[Dict]:
        """
        Generate prioritized list of recommendations.
        
        Args:
            findings: List of finding dictionaries
            
        Returns:
            Sorted list of unique recommendations with priorities
        """
        recommendations = []
        
        # Priority sorting
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        
        for finding in findings:
            rec_data = finding.get('recommendations', {})
            if rec_data:
                recommendations.append({
                    'spot_number': finding['spot_number'],
                    'type': finding['type'],
                    'advice': rec_data.get('advice', []),
                    'savings': rec_data.get('savings', ''),
                    'priority': rec_data.get('priority', 'medium'),
                    'severity': finding['severity']
                })
        
        # Sort by priority then severity
        severity_index = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        recommendations.sort(key=lambda x: (
            priority_order.get(x['priority'], 2),
            -severity_index.get(x['severity'], 0)
        ))
        
        return recommendations
