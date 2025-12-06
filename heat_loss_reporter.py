#!/usr/bin/env python3
"""
Heat Loss Reporter - Professional thermal survey report generation
Focuses on heat loss assessment and energy-saving recommendations
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from security_utils import validate_batch_id
from security_utils import validate_batch_id

class HeatLossReporter:
    """
    Generate professional heat loss reports for building thermal surveys.
    
    Takes labeled hot spots from thermal images and creates comprehensive
    reports with energy-saving recommendations following the structure of
    thermal_survey_example.pdf.
    """
    
    def __init__(self, recommendations_file='energy_recommendations.json'):
        """
        Initialize reporter with energy-saving recommendations database.
        
        Args:
            recommendations_file: Path to JSON file with recommendations by type
        """
        self.recommendations_file = Path(recommendations_file)
        self.recommendations = self._load_recommendations()
    
    def _load_recommendations(self) -> Dict:
        """Load energy-saving recommendations from JSON file"""
        if self.recommendations_file.exists():
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
    
    def load_batch_data(self, batch_id: str, reports_dir: str = 'reports') -> Dict:
        """
        Load all data for a batch including hot spot labels and thermal analysis.
        
        Args:
            batch_id: Unique batch identifier
            reports_dir: Base reports directory
            
        Returns:
            Dictionary with batch data
        """
        if not validate_batch_id(batch_id):
            raise ValueError(f"Invalid batch_id format: {batch_id}"
        batch_path = Path(reports_dir) / 'batches' / batch_id        
        # Load hot spot labels
        labels_file = batch_path / 'hotspot_labels.json'
        if not labels_file.exists():
            raise FileNotFoundError(f"Labels file not found: {labels_file}")
        
        with open(labels_file, 'r') as f:
            labels_data = json.load(f)
        
        return labels_data
    
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
        temps = [spot['temperature'] for spot in spot_group]
        max_temp = max(temps)
        min_temp = min(temps)
        avg_temp = sum(temps) / len(temps)
        
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
        description += f" Temperature readings range from {min_temp:.1f}°C to {max_temp:.1f}°C, "
        description += f"averaging {avg_temp:.1f}°C. "
        
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
            'images': [spot['image_name'] for spot in spot_group],
            'recommendations': recommendations,
            'spot_locations': [(spot['image_name'], spot['location']) for spot in spot_group]
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
            severity = finding['severity']
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
            'critical_count': severity_counts['critical'],
            'high_count': severity_counts['high']
        }
    
    def generate_recommendations_list(self, findings: List[Dict]) -> List[Dict]:
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
        recommendations.sort(key=lambda x: (
            priority_order.get(x['priority'], 2),
            -(['low', 'medium', 'high', 'critical'].index(x['severity']))
        ))
        
        return recommendations
    
    def generate_html_report(self, batch_id: str, property_address: str = "",
                            inspector_name: str = "", reports_dir: str = 'reports') -> str:
        """
        Generate complete HTML heat loss report.
        
        Args:
            batch_id: Unique batch identifier
            property_address: Property address for report
            inspector_name: Inspector name for report
            reports_dir: Base reports directory
            
        Returns:
            Path to generated HTML report
        """
        # Load batch data
        batch_data = self.load_batch_data(batch_id, reports_dir)
        labeled_spots = batch_data.get('labeled_spots', [])
        
        # Group by spot number
        grouped_spots = self.group_by_spot_number(labeled_spots)
        
        # Generate findings
        findings = []
        for spot_num in sorted(grouped_spots.keys()):
            finding = self.generate_finding_narrative(grouped_spots[spot_num], spot_num)
            findings.append(finding)
        
        # Generate summary
        summary = self.generate_executive_summary(findings)
        
        # Generate recommendations
        recommendations = self.generate_recommendations_list(findings)
        
        # Prepare report data
        report_data = {
            'batch_id': batch_id,
            'property_address': property_address or 'Not specified',
            'inspector_name': inspector_name or 'Not specified',
            'survey_date': datetime.now().strftime('%Y-%m-%d'),
            'survey_time': datetime.now().strftime('%H:%M'),
            'summary': summary,
            'findings': findings,
            'recommendations': recommendations
        }
        
        # Save report data
        batch_path = Path(reports_dir) / 'batches' / batch_id
        report_data_file = batch_path / 'heat_loss_report_data.json'
        with open(report_data_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        return str(report_data_file)
