# Heat Loss Report Implementation Plan

## Overview
Implement a two-step Flask workflow for thermal imaging heat loss assessment, focused on building energy efficiency surveys. This system will collate thermal data from batch images and generate professional heat loss reports with energy-saving recommendations.

## Critical Requirements (User Verbatim)
- "these images are assessing heat loss and that is what we are reporting on"
- Two-step process: (1) Hot spot labeling, (2) Report generation
- Hot spots need naming with dropdowns: Window, Door, Wall, Eaves, Vent, Roof, Chimney, Porch
- Hot spots need numbering for cross-image identification
- "when an operator can see that a point is visible in two or more photographs, it will be helpful to report on that"
- Energy-saving advice based on hot spot type
- Follow thermal_survey_example.pdf report structure from main branch

## System Architecture

### Step 1: Hot Spot Labeling Interface
**Purpose:** Allow operators to categorize and number detected thermal anomalies

**Features:**
- Display all processed images from batch with detected hot spots highlighted
- For each hot spot:
  - Dropdown selector for type: Window, Door, Wall, Eaves, Vent, Roof, Chimney, Porch
  - Number field (1-99) for cross-image identification
  - Temperature display (from thermal_analyzer.py detection)
  - Severity indicator (from existing classification)
  - Location coordinates
- Visual interface showing:
  - Thumbnail of each image with hot spot markers
  - Ability to assign same number across multiple images
  - Summary of labeled hot spots

**Technical Implementation:**
- Route: `/label_hotspots/<batch_id>`
- Template: `templates/label_hotspots.html`
- Data stored in: `reports/<batch_id>/hotspot_labels.json`

### Step 2: Heat Loss Report Generation
**Purpose:** Generate professional thermal survey report with energy-saving recommendations

**Report Structure (based on thermal_survey_example.pdf):**
1. **Cover Page**
   - Property Address
   - Survey Date
   - Inspector Name
   - Company Logo
   - Survey description

2. **Executive Summary**
   - Number of findings
   - Highest anomaly severity
   - Survey duration
   - Overall assessment

3. **Survey Findings**
   - For each numbered hot spot:
     - Title (e.g., "Heat loss at Window #1")
     - Description of thermal anomaly
     - Max Temperature
     - Min Temperature  
     - Severity Level
     - Thermal Image
     - Visible Image (if available)
     - Cross-reference to other images showing same spot

4. **Technical Survey Details**
   - Camera Model
   - Resolution
   - Temperature Range
   - Survey Time
   - Ambient Temperature

5. **Recommendations**
   - Energy-saving advice per hot spot type
   - Priority order based on severity
   - Estimated heat loss impact

**Technical Implementation:**
- Module: `heat_loss_reporter.py`
- Route: `/generate_report/<batch_id>`
- Template: `templates/heat_loss_report.html`
- Output: `reports/<batch_id>/heat_loss_survey.html`

## Energy-Saving Recommendations Database

### By Hot Spot Type:

**Window:**
- "Install thermal curtains or cellular shades"
- "Add weather stripping around frame"
- "Consider secondary glazing or window film"
- "Check for gaps and seal with appropriate caulk"
- "Potential savings: 10-20% on heating costs"

**Door:**
- "Install or replace door sweep at bottom"
- "Add weather stripping to frame"
- "Consider thermal door curtain"
- "Check threshold and seal gaps"
- "Potential savings: 5-10% on heating costs"

**Wall:**
- "Inspect cavity insulation levels"
- "Consider external or internal wall insulation"
- "Check for thermal bridging at structural elements"
- "Investigate damp or missing insulation"
- "Potential savings: 15-35% on heating costs"

**Eaves:**
- "Improve loft insulation to 270mm depth"
- "Seal gaps between wall and roof"
- "Check for ventilation/insulation balance"
- "Install eaves insulation baffles"
- "Potential savings: 20-30% on heating costs"

**Vent:**
- "Install controllable trickle vents"
- "Check if vent is necessary or can be sealed"
- "Consider heat recovery ventilation"
- "Ensure vent serves its intended purpose"
- "Potential savings: 5-10% on heating costs"

**Roof:**
- "Increase loft insulation depth"
- "Check for gaps or compressed insulation"
- "Inspect roof tiles for damage"
- "Consider warm roof construction for flat roofs"
- "Potential savings: 25-35% on heating costs"

**Chimney:**
- "Install chimney balloon or cap when not in use"
- "Consider chimney sheep draught excluder"
- "Seal around fireplace opening"
- "Check flue damper operation"
- "Potential savings: 5-15% on heating costs"

**Porch:**
- "Create thermal air-lock with second door"
- "Improve porch insulation"
- "Seal gaps around door frames"
- "Consider enclosed porch addition"
- "Potential savings: 5-10% on heating costs"

## Data Flow

```
1. User uploads batch images → process_batch()
2. thermal_analyzer.py detects hot spots
3. Store hot spot data in batch results
4. Redirect to /label_hotspots/<batch_id>
5. Operator assigns types and numbers
6. Save labels to hotspot_labels.json
7. Click "Generate Report" → /generate_report/<batch_id>
8. heat_loss_reporter.py:
   - Load hot spot data + labels
   - Group by spot number
   - Generate narrative for each
   - Add energy-saving recommendations
   - Create HTML report
9. Display/download final report
```

## Files to Create/Modify

### New Files:
1. `heat_loss_reporter.py` - Report generation module
2. `templates/label_hotspots.html` - Labeling interface
3. `templates/heat_loss_report.html` - Final report template
4. `energy_recommendations.json` - Recommendations database

### Modified Files:
1. `app.py` - Add routes:
   - `/label_hotspots/<batch_id>`
   - `/save_labels/<batch_id>` (POST)
   - `/generate_report/<batch_id>`
   - `/view_heat_loss_report/<batch_id>`

2. `process_batch()` - Store hot spot data in structured format

## Data Structures

### hotspot_labels.json
```json
{
  "batch_id": "batch_20251128_140000",
  "labeled_spots": [
    {
      "spot_id": "img1_spot1",
      "spot_number": 1,
      "type": "Window",
      "image_name": "FLIR0001.jpg",
      "location": [120, 350],
      "temperature": 15.2,
      "severity": "high"
    },
    {
      "spot_id": "img2_spot1",
      "spot_number": 1,
      "type": "Window",
      "image_name": "FLIR0002.jpg",
      "location": [200, 300],
      "temperature": 14.8,
      "severity": "high"
    }
  ],
  "cross_references": {
    "1": ["img1_spot1", "img2_spot1"]
  }
}
```

## Implementation Priority

1. ✅ Create branch heat-loss-report
2. ⏳ Create this design document
3. Create `heat_loss_reporter.py` module
4. Create `energy_recommendations.json`
5. Modify `app.py` - add labeling route
6. Create `label_hotspots.html` template
7. Modify `app.py` - add report generation route  
8. Create `heat_loss_report.html` template
9. Test complete workflow
10. Document in README

## Testing Checklist

- [ ] Upload batch with 6-8 images
- [ ] Verify hot spots detected correctly
- [ ] Label hot spots with different types
- [ ] Assign same number to spots visible in multiple images
- [ ] Generate heat loss report
- [ ] Verify report structure matches thermal_survey_example.pdf
- [ ] Confirm energy-saving recommendations appear correctly
- [ ] Verify cross-references work for multi-image hot spots
- [ ] Check report is professional and readable
- [ ] Test download functionality

## Notes

- Remember: Focus is on HEAT LOSS assessment, not just hot spots
- Language should emphasize energy efficiency and cost savings
- Report must be suitable for homeowners (non-technical)
- Professional appearance following thermal_survey_example.pdf
- Cross-image identification is critical for complete assessment
