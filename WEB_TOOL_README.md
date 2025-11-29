# Web Interface for Thermal Report Processing

This document describes the web-based tool for batch uploading and processing FLIR thermal images.

## Overview

The web interface provides a convenient way to:
- Upload batches of 6-8 FLIR thermal images
- Automatically process them through the thermal report generation pipeline
- Browse and download generated reports
- View all processed batches in a centralized index

## Setup

### Prerequisites

Ensure you have completed the basic setup from the main README:
1. Python 3.x installed
2. ExifTool installed and accessible in PATH
3. All Python dependencies installed: `pip install -r requirements.txt`

### Additional Web Interface Dependencies

The web interface requires Flask:

```bash
pip install flask
```

This is already included in `requirements.txt` if you install dependencies as shown above.

### Directory Structure

The web tool uses these directories:
- `Images/` - Stores uploaded thermal image files
- `reports/` - Stores generated HTML reports and associated files

These directories are created automatically when you run the web tool.

## Running the Web Interface

### Starting the Server

From the project root directory:

```bash
python app.py
```

The server will start on `http://localhost:5000`

You should see output similar to:
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### Accessing the Interface

Open your web browser and navigate to:
```
http://localhost:5000
```

## Using the Web Interface

### Uploading and Processing Images

1. **Navigate to the home page** (`http://localhost:5000`)

2. **Select your FLIR images**:
   - Click the "Choose Files" button
   - Select 6-8 FLIR thermal images (`.jpg` format)
   - The interface accepts batches of 6-8 images for optimal processing

3. **Upload and process**:
   - Click the "Upload and Process" button
   - The system will:
     - Upload your images to the `Images/` directory
     - Run the thermal report generation script
     - Create HTML reports in the `reports/` directory
     - Generate a unique batch ID with timestamp

4. **Wait for processing**:
   - Processing time depends on the number of images and system performance
   - You'll see a success message when complete

### Viewing Reports

**From the Index Page**:

After processing, the index page displays all available report batches:
- Batch ID (timestamp-based)
- Number of images processed
- Processing date/time
- Links to view or download each report

**Report Navigation**:

1. Click "View" next to any batch to see the generated report
2. Reports include:
   - Thermal images with temperature data
   - Metadata extracted via ExifTool
   - Temperature statistics and analysis
   - Visual overlays and annotations

**Downloading Reports**:

- Click "Download" to save the HTML report file locally
- Reports can be opened offline in any web browser

## Workflow Example

### Complete Batch Processing Workflow:

1. **Prepare your images**:
   ```
   - Collect 6-8 FLIR thermal images from your inspection
   - Ensure files are in `.jpg` format
   - Name files descriptively (e.g., `panel_01.jpg`, `panel_02.jpg`)
   ```

2. **Start the web server**:
   ```bash
   python app.py
   ```

3. **Upload batch**:
   - Open browser to `http://localhost:5000`
   - Click "Choose Files"
   - Select your 6-8 images
   - Click "Upload and Process"

4. **Review results**:
   - Wait for processing confirmation
   - View the newly created batch in the index
   - Click "View" to inspect the report
   - Download if needed for offline review or sharing

5. **Repeat for additional batches**:
   - Upload more batches as needed
   - All batches remain accessible from the index page
   - Each batch is stored separately with a unique ID

## File Organization

### Images Directory (`Images/`)

Uploaded images are stored in batch subdirectories:
```
Images/
├── batch_20250101_143022/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── ...
├── batch_20250101_150133/
│   └── ...
```

### Reports Directory (`reports/`)

Generated reports are organized by batch:
```
reports/
├── batch_20250101_143022/
│   ├── index.html
│   ├── image1_report.html
│   ├── image2_report.html
│   └── ...
├── batch_20250101_150133/
│   └── ...
```

## Technical Details

### Backend (app.py)

- **Framework**: Flask
- **Routes**:
  - `/` - Index page showing all processed batches
  - `/upload` - Handles file upload and processing
  - `/report/<batch_id>` - Displays specific batch report
  - `/download/<batch_id>` - Downloads report as file

### Processing Pipeline

1. **Upload**: Files uploaded via multipart form data
2. **Validation**: Checks file types and count (6-8 images)
3. **Storage**: Saves to batch-specific subdirectory in `Images/`
4. **Processing**: Executes the thermal report generation script
5. **Indexing**: Updates batch index for web display
6. **Rendering**: Serves reports via Flask templates

### Templates

- `templates/index.html` - Main landing page with batch list
- `templates/report.html` - Report viewer page

## Troubleshooting

### Common Issues

**Port Already in Use**:
```
OSError: [Errno 48] Address already in use
```
Solution: Stop other Flask instances or change port in `app.py`:
```python
app.run(debug=True, port=5001)
```

**ExifTool Not Found**:
```
Error: exiftool not found in PATH
```
Solution: Install ExifTool and ensure it's accessible:
- Mac: `brew install exiftool`
- Linux: `sudo apt-get install libimage-exiftool-perl`
- Windows: Download from official site and add to PATH

**Permission Errors**:
```
PermissionError: [Errno 13] Permission denied: 'Images/'
```
Solution: Ensure write permissions for `Images/` and `reports/` directories

**Upload Fails**:
- Check that you're uploading 6-8 images
- Verify images are in `.jpg` format
- Ensure file sizes are reasonable (<50MB per image)

**Reports Not Displaying**:
- Verify the processing script completed successfully
- Check the `reports/` directory for generated HTML files
- Review Flask console output for error messages

## Security Considerations

⚠️ **Important**: This web tool is designed for local use only.

- **Do not expose to the public internet** without proper security measures
- No authentication is implemented
- File uploads are not sanitized beyond basic type checking
- Suitable for local development and testing environments

For production deployment:
- Implement user authentication
- Add CSRF protection
- Validate and sanitize all uploads
- Use a production WSGI server (e.g., Gunicorn, uWSGI)
- Configure proper firewall rules

## API Reference

### Upload Endpoint

**POST** `/upload`

Uploads and processes a batch of thermal images.

**Parameters**:
- `files`: MultipartFile array (6-8 .jpg images)

**Response**:
- Success: Redirects to index with batch ID
- Error: Returns error message

**Example** (curl):
```bash
curl -X POST -F "files=@image1.jpg" -F "files=@image2.jpg" \
  http://localhost:5000/upload
```

### Report Endpoint

**GET** `/report/<batch_id>`

Displays the report for a specific batch.

**Parameters**:
- `batch_id`: Unique batch identifier (timestamp-based)

**Response**:
- HTML report page

### Download Endpoint

**GET** `/download/<batch_id>`

Downloads the report as an HTML file.

**Parameters**:
- `batch_id`: Unique batch identifier

**Response**:
- HTML file download

## Future Enhancements

- Real-time processing status updates
- Batch deletion functionality
- Report comparison tools
- Advanced filtering and search
- Batch processing queue for large datasets
- RESTful API for integration with other tools
- Export to PDF format
- Image annotation and markup tools

## Support

For issues or questions:
1. Check the main project README
2. Review TESTING.md for testing procedures
3. Open an issue on the GitHub repository

## License

This tool is part of the thermal-report project. See the main README for license information.
