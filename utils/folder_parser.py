"""
Folder name parser for survey results.

Parses folder names following the convention:
AddressPart-WithHyphens_OwnerInitials-Ref_Surveyor1_Surveyor2(_Surveyor3)
Example: 100-Chartridge-Lane_CH-0501_MF_JD  - Address: 100 Chartridge Lane
  - Owner Initials: CH
  - Reference: 0501
  - Surveyor 1: MF (Mark)
  - Surveyor 2: JD (Jon)
"""

import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class SurveyFolderInfo:
    """Parsed survey folder information."""
    raw_name: str
    address: str
    owner_initials: str  # tenant_id equivalent
    reference_number: str
    surveyor1_initials: str
    surveyor2_initials: Optional[str] = None
    surveyor3_initials: Optional[str] = None
    is_processed: bool = False


def parse_folder_name(folder_name: str) -> Optional[SurveyFolderInfo]:
    """
    Parse a survey folder name into its components.
    
    Handles formats:
    - 100-Chartridge-Lane_CH-0501_MF_JD    - Blazing-Saddles-Chartridge-Lane-100CH-0501MFJD
    - Blazing-Saddles-Chartridge-Lane-100_CH-0501_MF_JD    
    - _100-Chartridge-Lane_CH-0501_MF_JD (processed, starts with underscore)        folder_name: The folder name to parse
    
    Returns:
        SurveyFolderInfo object if parsing successful, None otherwise
    """
    # Check if folder has been processed (starts with underscore)
    is_processed = folder_name.startswith('_')
    clean_name = folder_name.lstrip('_')
    
    # Pattern to match the folder naming convention
    # This regex captures:
    # 1. Address parts (everything before owner initials)
    # 2. Owner initials (2-3 capital letters)
    # 3. Reference number (4 digits)
    # 4. Surveyor initials (2-4 capital letters for one or two surveyors)
    pattern = r'^(.+?)([A-Z]{2,3})-([0-9]{4})([A-Z]{2,4})$'
    
    match = re.match(pattern, clean_name)
    
    if not match:
    # Format: Address_OwnerInitials-Ref_Surveyor1_Surveyor2(_Surveyor3)
    # Split by underscores to get main parts
    parts = clean_name.split('_')
    
    if len(parts) < 3:  # Need at least: Address, OwnerInit-Ref, Surveyor1
        return None
    
    address_raw = parts[0]
    owner_ref = parts[1]  # e.g., "CH-0501"
    surveyors = parts[2:]  # e.g., ["MF", "JD"] or ["MF", "JD", "AO"]
    
    # Parse owner initials and reference number
    if '-' not in owner_ref:
        return None
    
    owner_parts = owner_ref.split('-')
    if len(owner_parts) != 2:
        return None
    
    owner_initials = owner_parts[0]
    reference_number = owner_parts[1]
    
    # Clean up address: replace hyphens with spaces
    address = address_raw.replace('-', ' ')
    
    # Parse surveyors (should be 2-letter initials each)
    surveyor1 = surveyors[0] if len(surveyors) >= 1 else None
    surveyor2 = surveyors[1] if len(surveyors) >= 2 else None
    surveyor3 = surveyors[2] if len(surveyors) >= 3 else None
    
    return SurveyFolderInfo(
        raw_name=folder_name,
    return SurveyFolderInfo(
        raw_name=folder_name,
        address=address,
        owner_initials=owner_initials,
        reference_number=reference_number,
        surveyor1_initials=surveyor1,
        surveyor2_initials=surveyor2,
        surveyor3_initials=surveyor3,
        is_processed=is_processed
    )
def format_surveyor_names(info: SurveyFolderInfo, surveyor_map: Optional[Dict[str, str]] = None) -> str:
    """
    Format surveyor names for use in reports.
    
    Args:
        info: Parsed folder information
        surveyor_map: Optional mapping of initials to full names
    
    Returns:
        Formatted string like "MF and JD" or "Mark and Jon"
    """
    
    if info.surveyor3_initials:
        s3 = surveyor_map.get(info.surveyor3_initials, info.surveyor3_initials) if surveyor_map else info.surveyor3_initials
        return f"{s1}, {s2}, and {s3}"
    s1 = surveyor_map.get(info.surveyor1_initials, info.surveyor1_initials) if surveyor_map else info.surveyor1_initials
    
    if info.surveyor2_initials:
        s2 = surveyor_map.get(info.surveyor2_initials, info.surveyor2_initials) if surveyor_map else info.surveyor2_initials
        return f"{s1} and {s2}"
    
    return s1


def get_tenant_id_from_folder(folder_name: str) -> Optional[str]:
    """
    Extract tenant_id (owner initials) from folder name.
    This can be used as the homeowner identifier.
    
    Args:
        folder_name: The folder name to parse
        
    Returns:
        Owner initials (tenant_id) or None
    """
    info = parse_folder_name(folder_name)
    return info.owner_initials if info else None
