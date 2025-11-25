#!/usr/bin/env python3
"""
Automated test suite for thermal-report
Runs comprehensive tests to verify environment setup and functionality.
"""
import os
import sys

def test_dependencies():
    """Test if all dependencies are installed"""
    print("\n" + "="*60)
    print("TEST 1: Checking Python Dependencies")
    print("="*60)
    
    dependencies = {
        'numpy': 'NumPy',
        'PIL': 'Pillow',
        'flirimageextractor': 'FlirImageExtractor',
        'matplotlib': 'Matplotlib'
    }
    
    all_installed = True
    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"✓ {name} is installed")
        except ImportError:
            print(f"✗ {name} is NOT installed")
            all_installed = False
    
    if all_installed:
        print("\n✓ All Python dependencies are installed")
    else:
        print("\n✗ Some dependencies are missing")
        print("\nInstall missing packages with:")
        print("  pip install -r requirements.txt")
    
    return all_installed

def test_exiftool():
    """Test if exiftool is available"""
    print("\n" + "="*60)
    print("TEST 2: Checking ExifTool")
    print("="*60)
    
    import subprocess
    try:
        result = subprocess.run(['exiftool', '-ver'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ ExifTool is installed (version {result.stdout.strip()})")
            return True
        else:
            print("✗ ExifTool command failed")
            return False
    except FileNotFoundError:
        print("✗ ExifTool is NOT installed")
        print("\nInstall ExifTool:")
        print("  Debian/Ubuntu: sudo apt install libimage-exiftool-perl")
        print("  macOS: brew install exiftool")
        print("  Windows: Download from https://exiftool.org/")
        return False
    except subprocess.TimeoutExpired:
        print("✗ ExifTool command timed out")
        return False

def test_sample_image():
    """Test processing sample image"""
    print("\n" + "="*60)
    print("TEST 3: Processing Sample FLIR Image")
    print("="*60)
    
    # Check if test image exists
    if not os.path.exists('FLIR0648.jpg'):
        print("✗ Test image FLIR0648.jpg not found in repository root")
        return False
    
    print("✓ Test image FLIR0648.jpg found")
    
    try:
        from flir_processor_simple import SimpleFLIRProcessor
        print("✓ SimpleFLIRProcessor imported successfully")
        
        processor = SimpleFLIRProcessor()
        print("✓ Processor initialized")
        
        print("\nProcessing image (this may take a moment)...")
        temp_data, stats = processor.process_single_image(
            'FLIR0648.jpg', display=False
        )
        
        print(f"\n✓ Image processed successfully!")
        print(f"  - Image shape: {temp_data.shape[0]} x {temp_data.shape[1]} pixels")
        print(f"  - Temperature range: {stats['min']:.1f}°C to {stats['max']:.1f}°C")
        print(f"  - Mean temperature: {stats['mean']:.1f}°C")
        print(f"  - Median temperature: {stats['median']:.1f}°C")
        print(f"  - Standard deviation: {stats['std']:.1f}°C")
        
        return True
    except ImportError as e:
        print(f"✗ Failed to import required module: {e}")
        return False
    except Exception as e:
        print(f"✗ Error processing image: {e}")
        return False

def test_file_operations():
    """Test file export operations"""
    print("\n" + "="*60)
    print("TEST 4: File Export Operations")
    print("="*60)
    
    try:
        import numpy as np
        from flir_processor_simple import SimpleFLIRProcessor
        
        processor = SimpleFLIRProcessor()
        temp_data, _ = processor.process_single_image('FLIR0648.jpg', display=False)
        
        # Test CSV export
        csv_file = 'test_output.csv'
        processor.save_temperature_array(temp_data, csv_file)
        if os.path.exists(csv_file):
            print(f"✓ CSV export successful: {csv_file}")
            os.remove(csv_file)  # Cleanup
        else:
            print(f"✗ CSV export failed")
            return False
        
        # Test NPY export
        npy_file = 'test_output.npy'
        processor.save_temperature_array(temp_data, npy_file)
        if os.path.exists(npy_file):
            print(f"✓ NPY export successful: {npy_file}")
            os.remove(npy_file)  # Cleanup
        else:
            print(f"✗ NPY export failed")
            return False
        
        print("\n✓ All file operations successful")
        return True
        
    except Exception as e:
        print(f"✗ File operation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("#  THERMAL REPORT - AUTOMATED TEST SUITE")
    print("#"*60)
    
    tests = [
        ("Python Dependencies", test_dependencies),
        ("ExifTool", test_exiftool),
        ("Sample Image Processing", test_sample_image),
        ("File Export Operations", test_file_operations)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "#"*60)
    print("#  TEST SUMMARY")
    print("#"*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{total} tests passed ({passed*100//total}%)")
    print("="*60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your environment is ready.")
        print("\nNext steps:")
        print("  1. Place your FLIR images in the ./Images folder")
        print("  2. Run: python flir_batch_processor.py ./Images")
        print("  3. Check the ./reports folder for results")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nFor help, see TESTING.md or visit:")
        print("  https://github.com/jondendy/thermal-report")
        sys.exit(1)

if __name__ == '__main__':
    main()
