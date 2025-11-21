from flir_processor_simple import SimpleFLIRProcessor

processor = SimpleFLIRProcessor()

# Process image
temp_data, stats = processor.process_single_image('test_images/FLIR0648.jpg')

# Temperature data is a 2D numpy array in Celsius
print(f"Shape: {temp_data.shape}")
print(f"Min temp: {stats['min']:.2f} °C")
print(f"Max temp: {stats['max']:.2f} °C")
print(f"Mean temp: {stats['mean']:.2f} °C")
print(f"Median temp: {stats['median']:.2f} °C")
print(f"Std dev: {stats['std']:.2f} °C")

# Access individual pixel temperatures
temp_at_pixel = temp_data[100, 150]  # row 100, column 150
print(f"Temperature at pixel (100, 150): {temp_at_pixel:.2f} °C")

# Find hottest and coldest points
hot_spot = np.unravel_index(np.argmax(temp_data), temp_data.shape)
cold_spot = np.unravel_index(np.argmin(temp_data), temp_data.shape)
print(f"Hottest point: {hot_spot}, {temp_data[hot_spot]:.2f} °C")
print(f"Coldest point: {cold_spot}, {temp_data[cold_spot]:.2f} °C")
