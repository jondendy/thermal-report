# Thermal Report App — Fix Plan & Progress Tracker

Last updated: 2026-03-10

---

## Status Key
- ✅ Done
- 🔄 In Progress
- ⬜ Not Started

---

## Fix Items

### 1. ✅ Fix report image generation (excessive images)
**Problem:** One image was being embedded per spot occurrence, causing duplicates.
**Solution:** Group `spot_locations` by source image so each image appears only once per finding.
**Files changed:** `services/heat_loss_reporter.py`, `services/heat_loss_service.py`
**Committed:** `327297c` — *Fix excessive images in report*

---

### 2. ⬜ Fix default temperature for manually added spots
**Problem:** When a surveyor manually clicks to add a spot, the temperature defaults to a hardcoded value (20.0°C) rather than reading the actual thermal data at those pixel coordinates.
**Solution:**
- On image click in `edit_spots.html`, send the (x, y) coordinates to a new API endpoint
- New endpoint reads the corresponding `_temperatures.csv` for that image and returns the actual temperature at that pixel
- Update the modal pre-fill to use the returned temperature
**Files to change:** `templates/edit_spots.html`, `app.py`

---

### 2.5. ⬜ Ensure batch folders have correct write permissions
**Problem:** Batch report directories may lack write permissions, causing file creation to fail silently.
**Solution:**
- Verify `.reports/batch_*/` directories are writable at creation time
- Add explicit `chmod 755` when creating batch directories
- Update `safe_batch_path()` in `security_utils.py` to set permissions
**Files to change:** `security_utils.py`

---

### 3. ⬜ Add new spot types with descriptions
**Problem:** Current spot types are limited; surveyors need Eaves, Utilities, Chimney, Sills.
**Solution:**
- Add `Eaves`, `Utilities`, `Chimney`, `Sills` to `SPOT_TYPES` in `app.py`
- Add matching entries with advice, savings estimates and priority to `_get_default_recommendations()` in `services/heat_loss_reporter.py`
**Files to change:** `app.py`, `services/heat_loss_reporter.py`

---

### 4. ⬜ Add surveyor notes field
**Problem:** Surveyors have no way to add free-text notes that appear in the report.
**Solution:**
- Add a `<textarea>` for notes in `edit_spots.html` Survey Information section
- Save to `hotspotlabels.json` alongside `property_address` and `surveyor_name`
- Render notes in a dedicated section of the PDF report
**Files to change:** `templates/edit_spots.html`, `services/heat_loss_service.py`

---

### 5. ⬜ Use photo timestamp for report date
**Problem:** Report date uses `datetime.now()` (server time) rather than the actual survey date from the thermal images.
**Solution:**
- Extract EXIF `DateTimeOriginal` from FLIR images using `exiftool` or `Pillow`
- Use earliest image timestamp as the survey date
- Fall back to `datetime.now()` if EXIF unavailable
**Files to change:** `services/heat_loss_service.py`

---

### 6. ⬜ Organisation details in report footer
**Problem:** Report footer shows placeholder values (`Your Survey Organisation`, `https://example.com`) instead of real org details.
**Solution:**
- Ensure `ORG_NAME`, `ORG_WEBSITE`, `ORG_CONTACT` are set in `.env`
- Confirm they flow correctly from `settings.py` → `generate_report()` → `_render_report_html()`
- Document required `.env` variables in `README`
**Files to change:** `.env` (config), `README.md`

---

### 7. ✅ Embed recommendations document inline in PDF
**Problem:** The recommendations document was only shown as a clickable link, not embedded in the PDF.
**Solution:**
- Added `_download_google_drive_pdf()` to fetch PDFs from Google Drive using direct download URL
- Added `_merge_recommendations_pdf()` using `pypdf` to append pages to the report PDF
- Added `_merge_additional_pdfs()` to handle multiple PDFs (Recommendations + Tips)
- Added PDF selector checkboxes to `edit_spots.html` UI
- Added `TIPS_DOCUMENT_URL` to `settings.py`
- Fixed `load_dotenv()` missing from `settings.py`
- Removed duplicate `RECOMMENDATIONS_DOCUMENT_URL = ""` override in `settings.py`
**Files changed:** `services/heat_loss_service.py`, `settings.py`, `templates/edit_spots.html`, `requirements.txt`
**Committed:** `b041f73`, `9d3679b`, `515f2c7`

---

### 8. ✅ Manual spot labels shown in PDF images
**Problem:** PDF images showed automatic hotspot detection markers, not the surveyor's manually numbered red circles.
**Solution:**
- Added `draw_manual_labels()` to `ThermalAnalyzer` — draws red circles with white spot numbers
- Added `_regenerate_labeled_images_with_manual_spots()` to regenerate `_labeled.jpg` files before PDF creation
- Fixed image path lookup to check `.Images/` folder for original FLIR files
**Files changed:** `services/thermal_analyzer.py`, `services/heat_loss_service.py`
**Committed:** `b041f73`

---

### 9. ✅ Fix spot grouping: Door #6 ≠ Window #6 ≠ Wall #6
**Problem:** `group_by_spot_number()` only grouped by number, merging different types with the same number into one finding.
**Solution:**
- Changed grouping key from `spot_number` to composite `f"{type}_{spot_number}"`
- Updated `generate_finding_narrative()` to extract actual `spot_number` from the group
- Updated call site in `heat_loss_service.py`
**Files changed:** `services/heat_loss_reporter.py`, `services/heat_loss_service.py`
**Committed:** `9d3679b`

---

### 10. ⬜ Review & Narrate step (new page in survey workflow)
**Problem:** After labelling spots, the surveyor goes straight to PDF generation with no opportunity to review or annotate the auto-generated findings text. Surveyors need to be able to review each finding alongside its thermal image, edit the generated narrative, add their own notes, and adjust or soften wording before the report is finalised.

**New workflow step:** `edit_spots` → **`review_report`** → `generate PDF`

**Solution:**
- Create new route `/review_report/<batch_id>` and template `templates/review_report.html`
- Page layout: two-column per finding — thermal image (left) + editable narrative text (right)
- Fields editable per finding:
  - Description / narrative (pre-filled from `generate_finding_narrative()`)
  - Surveyor note (free-text, appended below description in PDF)
  - Severity override (dropdown — allow surveyor to downgrade if appropriate)
- A global notes field at the top for general surveyor comments
- "Generate PDF" button at the bottom submits all edits
- Edited narratives and notes saved back to `hotspotlabels.json` under a `review` key
- `_render_report_html()` uses reviewed text in preference to auto-generated text

**Files to create/change:**
- `templates/review_report.html` (new)
- `app.py` — add `/review_report/<batch_id>` GET and POST routes
- `services/heat_loss_service.py` — save/load reviewed narratives
- `services/batch_io.py` — persist review data
- `templates/edit_spots.html` — change "Generate Report" button to go to `/review_report/` instead

---

## Remaining Work Summary

| # | Item | Effort |
|---|------|--------|
| 2 | Real temperature for manually placed spots | Medium |
| 2.5 | Batch folder write permissions | Small |
| 3 | New spot types (Eaves, Chimney, Sills, Utilities) | Small |
| 4 | Surveyor notes field | Small (absorbed into #10) |
| 5 | EXIF photo timestamp for survey date | Small |
| 6 | Org details in footer | Small |
| 10 | Review & Narrate step | Medium |

---

## Branch Notes
- Active development branch: `testbed/main-flat-safe-pdf`
- Stable branch: `feature/folder-naming-workflow` (cherry-picked up to `9d3679b`)
- Both branches are in sync as of 2026-03-10
