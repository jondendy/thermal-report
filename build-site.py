import os
import glob
import base64
from flir_processor_simple import SimpleFLIRProcessor
from io import BytesIO

# Initialize the FLIR processor
processor = SimpleFLIRProcessor()

def create_report_card(image_path):
    """
    Processes a single FLIR image and generates an HTML card containing
    statistics and a Base64-encoded version of the thermal image plot.
    """
    try:
        # 1. Process the image to get temperature data and statistics
        temp_data, stats = processor.process_single_image(image_path, display=False)
        
        # 2. Generate a visualization and get the image data (as a Base64 string)
        # We need a slight modification to the processor to get the plot data without saving a file
        
        # This part requires an internal function or modification to SimpleFLIRProcessor 
        # to return the plot as a file object or Base64 string. Since I don't have
        # the internal code, I will simulate getting the Base64 image using a placeholder 
        # or assuming the processor has a method to get the plot as bytes/base64.
        
        # --- SIMULATION START: Replace this with your actual visualization code ---
        
        # For a truly runnable example, we will save the plot to a temporary buffer
        # and convert it to Base64. This requires matplotlib to be imported.
        
        import matplotlib.pyplot as plt
        
        # Create a simple plot of the thermal data (using the simplest version for testing)
        plt.figure(figsize=(6, 4))
        plt.imshow(temp_data, cmap='inferno')
        plt.colorbar(label='Temperature (°C)')
        plt.title(os.path.basename(image_path))
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        # --- SIMULATION END ---

        return f"""
        <div class="p-6 bg-white rounded-xl shadow-lg hover:shadow-xl transition duration-300">
            <h2 class="text-2xl font-bold mb-4 text-gray-800">{os.path.basename(image_path)}</h2>
            <div class="flex flex-col md:flex-row gap-4">
                <div class="md:w-1/2">
                    <img src="data:image/png;base64,{img_base64}" alt="Thermal Image Plot" class="w-full h-auto rounded-lg shadow-md border-2 border-gray-100">
                </div>
                <div class="md:w-1/2">
                    <h3 class="text-xl font-semibold mb-2 text-indigo-600">Thermal Statistics</h3>
                    <ul class="space-y-1 text-gray-700">
                        <li><span class="font-medium">Min Temp:</span> <span class="text-red-700 font-mono">{stats['min']:.2f} °C</span></li>
                        <li><span class="font-medium">Max Temp:</span> <span class="text-red-700 font-mono">{stats['max']:.2f} °C</span></li>
                        <li><span class="font-medium">Mean Temp:</span> <span class="text-red-700 font-mono">{stats['mean']:.2f} °C</span></li>
                        <li><span class="font-medium">Median Temp:</span> <span class="text-red-700 font-mono">{stats['median']:.2f} °C</span></li>
                    </ul>
                </div>
            </div>
        </div>
        """

    except Exception as e:
        # If processing fails, return a simple error card
        print(f"ERROR: Failed to process {image_path}. Error: {e}")
        return f"""
        <div class="p-6 bg-red-100 rounded-xl shadow-lg border-2 border-red-500">
            <h2 class="text-2xl font-bold mb-4 text-red-800">{os.path.basename(image_path)} - ERROR</h2>
            <p class="text-red-700">Failed to generate thermal report. Check image format and dependencies.</p>
            <p class="text-red-500 text-sm mt-2">Error details: {e}</p>
        </div>
        """


def generate_index_html():
    """Main function to find images and create the index.html page."""
    
    print(f"DEBUG: Starting search for images...") 
    
    # Use glob to find all JPG files in the current directory
    # Note: If your images are in a subdirectory (e.g., './images/*.jpg'), adjust the path here.
    image_files = glob.glob("*.jpg")
    
    # Filter to ensure we only try to process the FLIR radiometric JPGs if possible
    # For now, we trust the glob, but you can add more complex filtering here.

    if not image_files:
        # Fallback if no images are found
        print("DEBUG: No JPG images found in the root directory.")
        cards_html = """
        <div class="text-center py-20">
            <h2 class="text-3xl font-extrabold text-gray-900">No Thermal Images Found</h2>
            <p class="mt-2 text-xl text-gray-600">Please ensure your FLIR JPG files are in the repository's root directory.</p>
        </div>
        """
    else:
        print(f"DEBUG: Found {len(image_files)} image files: {image_files}")
        
        # Generate HTML content for each image
        cards_html = "\n".join([create_report_card(f) for f in image_files])

    # Combine everything into the final HTML structure
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thermal Report Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f7f9fc;
        }}
    </style>
</head>
<body>
    <div class="min-h-screen p-4 md:p-8">
        <header class="text-center mb-10">
            <h1 class="text-5xl font-extrabold text-gray-900 tracking-tight">
                Automated Thermal Image Report
            </h1>
            <p class="mt-3 text-xl text-indigo-600">
                Data generated by `build-site.py` via GitHub Actions
            </p>
        </header>

        <main class="max-w-6xl mx-auto space-y-8">
            {cards_html}
        </main>

        <footer class="mt-10 pt-6 text-center text-sm text-gray-500 border-t border-gray-200">
            Deployment ID: {os.environ.get('GITHUB_RUN_ID', 'Local Run')} | Generated: {os.environ.get('GITHUB_SHA', 'Unknown Commit')}
        </footer>
    </div>
</body>
</html>
    """
    
    # CRITICAL STEP: Write the HTML file
    try:
        with open("index.html", "w") as f:
            f.write(html_content)
        print("DEBUG: index.html has been successfully written.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not write index.html. Error: {e}")


if __name__ == "__main__":
    generate_index_html()
