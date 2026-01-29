#!/usr/bin/env python3
"""
Extract thermal data from FLIR-based thermal images.

Supports: Skydio X10, Autel EVO II Dual, Yuneec H520E, Parrot Anafi Thermal,
and any drone using FLIR thermal sensors (Boson, Lepton, Tau).

DOES NOT work with DJI drones - use extract_thermal.js for DJI images.

Uses the FLIR Planck formula for temperature conversion.
"""

import sys
import subprocess
import json
import struct
import numpy as np
import csv
from pathlib import Path

def extract_flir_metadata(image_path):
    """Extract FLIR thermal metadata using exiftool."""
    result = subprocess.run(
        ['exiftool', '-flir:all', '-j', str(image_path)],
        capture_output=True,
        text=True,
        check=True
    )

    metadata = json.loads(result.stdout)[0]
    return metadata

def extract_raw_thermal_tiff(image_path):
    """Extract raw thermal TIFF data."""
    result = subprocess.run(
        ['exiftool', '-b', '-RawThermalImage', str(image_path)],
        capture_output=True,
        check=True
    )

    return result.stdout

def raw_to_temperature_flir_from_array(raw_array, metadata):
    """
    Convert FLIR raw sensor array to temperature using Planck formula.
    Input: numpy array of raw sensor values (uint16)
    """

    # Extract Planck constants from metadata
    def parse_float(value, default):
        """Parse float from string, removing units if present."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.split()[0]
            try:
                return float(value)
            except ValueError:
                return default
        return default

    R1 = parse_float(metadata.get('PlanckR1', 21106.77), 21106.77)
    B = parse_float(metadata.get('PlanckB', 1501), 1501)
    F = parse_float(metadata.get('PlanckF', 1), 1)
    O = parse_float(metadata.get('PlanckO', -7340), -7340)
    R2 = parse_float(metadata.get('PlanckR2', 0.012545258), 0.012545258)

    emissivity = parse_float(metadata.get('Emissivity', 0.95), 0.95)
    obj_distance = parse_float(metadata.get('ObjectDistance', 1.0), 1.0)

    print(f"\nUsing FLIR Planck parameters:")
    print(f"  R1: {R1}")
    print(f"  R2: {R2}")
    print(f"  B: {B}")
    print(f"  F: {F}")
    print(f"  O: {O}")
    print(f"  Emissivity: {emissivity}")
    print(f"  Distance: {obj_distance}m")

    # Apply FLIR Planck formula to entire array
    # T = B / ln(R1 / (R2 * (raw + O)) + F) - 273.15

    # Vectorized calculation
    with np.errstate(divide='ignore', invalid='ignore'):
        arg = R1 / (R2 * (raw_array.astype(float) + O)) + F
        arg = np.maximum(arg, 1e-10)  # Avoid log of zero
        temp_kelvin = B / np.log(arg)
        temp_celsius = temp_kelvin - 273.15

    return temp_celsius

def raw_to_temperature_flir(raw_data, width, height, metadata):
    """
    Convert FLIR raw sensor values to temperature using Planck formula.

    Formula from FLIR documentation:
    T = B / ln(R1 / (R2 * (raw + O)) + F) - 273.15

    Where:
    - R1, B, F: Planck constants from camera calibration
    - R2: Calculated from raw value
    - O: Offset (usually 0)
    - Result in Kelvin, subtract 273.15 for Celsius
    """

    # Extract Planck constants from metadata
    try:
        R1 = float(metadata.get('PlanckR1', 21106.77))
        B = float(metadata.get('PlanckB', 1501))
        F = float(metadata.get('PlanckF', 1))
        O = float(metadata.get('PlanckO', -7340))  # Offset
        R2 = float(metadata.get('PlanckR2', 0.012545258))
    except (ValueError, TypeError):
        print("Warning: Using default FLIR Planck constants")
        R1 = 21106.77
        B = 1501
        F = 1
        O = -7340
        R2 = 0.012545258

    # Additional parameters for atmospheric correction
    def parse_float(value, default):
        """Parse float from string, removing units if present."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common units and parse
            value = value.split()[0]  # Take first part before space
            try:
                return float(value)
            except ValueError:
                return default
        return default

    emissivity = parse_float(metadata.get('Emissivity', 0.95), 0.95)
    obj_distance = parse_float(metadata.get('ObjectDistance', 1.0), 1.0)
    atm_temp = parse_float(metadata.get('AtmosphericTemperature', 20.0), 20.0)
    refl_temp = parse_float(metadata.get('ReflectedApparentTemperature', 20.0), 20.0)
    humidity = parse_float(metadata.get('RelativeHumidity', 50.0), 50.0)

    print(f"\nUsing FLIR Planck parameters:")
    print(f"  R1: {R1}")
    print(f"  R2: {R2}")
    print(f"  B: {B}")
    print(f"  F: {F}")
    print(f"  O: {O}")
    print(f"  Emissivity: {emissivity}")
    print(f"  Distance: {obj_distance}m")

    # Parse TIFF data to get raw values
    # TIFF format: 16-bit unsigned integers
    num_pixels = width * height

    # Skip TIFF header (varies, but data typically starts after header)
    # For FLIR, raw thermal data is usually 16-bit little-endian
    try:
        # Try multiple offsets to find the thermal data
        offsets_to_try = [0, 8, 100, 500, 1000, 1500, 2000]
        raw_values = None

        for offset in offsets_to_try:
            data_size = len(raw_data) - offset
            num_values = data_size // 2

            if num_values >= num_pixels:
                try:
                    # Try unpacking with this offset
                    test_values = struct.unpack(f'<{num_pixels}H', raw_data[offset:offset + num_pixels * 2])

                    # Check if values seem reasonable (FLIR raw values are typically 10000-20000 range)
                    test_sample = test_values[:100]
                    avg_sample = sum(test_sample) / len(test_sample)

                    # Valid raw thermal data is usually in range 5000-30000
                    if 5000 < avg_sample < 30000:
                        raw_values = test_values
                        print(f"  Found thermal data at offset {offset}")
                        break
                except struct.error:
                    continue

        if raw_values is None:
            raise ValueError(f"Could not find valid thermal data. Expected {num_pixels} values.")

    except struct.error as e:
        print(f"Error parsing TIFF data: {e}")
        print(f"TIFF size: {len(raw_data)} bytes")
        print(f"Expected pixel data: {num_pixels * 2} bytes")
        return None

    # Convert raw values to temperature using FLIR formula
    temperatures = np.zeros(num_pixels)

    for i, raw in enumerate(raw_values):
        # FLIR Planck formula
        # Avoid division by zero
        if raw + O <= 0:
            temperatures[i] = -273.15  # Absolute zero as error value
        else:
            # T = B / ln(R1 / (R2 * (raw + O)) + F) - 273.15
            try:
                arg = R1 / (R2 * (raw + O)) + F
                if arg <= 0:
                    temperatures[i] = -273.15
                else:
                    temperatures[i] = B / np.log(arg) - 273.15
            except (ValueError, RuntimeWarning):
                temperatures[i] = -273.15

    # Apply emissivity correction (simplified)
    # More accurate atmospheric correction would require more complex calculations
    # temperatures = temperatures / emissivity

    return temperatures.reshape(height, width)

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_flir_thermal.py <image_path> [output_dir]")
        print("Example: python extract_flir_thermal.py data/thermal.jpg data/output")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else 'data/output')
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)

    print(f"Processing FLIR thermal image: {image_path}")

    # Extract metadata
    print("\nExtracting metadata...")
    metadata = extract_flir_metadata(image_path)

    width = metadata.get('RawThermalImageWidth', metadata.get('ImageWidth', 640))
    height = metadata.get('RawThermalImageHeight', metadata.get('ImageHeight', 512))

    print(f"Image dimensions: {width} x {height}")

    # Extract raw thermal data
    print("\nExtracting raw thermal data...")
    raw_data = extract_raw_thermal_tiff(image_path)
    print(f"Raw data size: {len(raw_data)} bytes")

    # Convert to temperatures
    print("\nConverting to temperatures...")

    # Use PIL to parse TIFF properly
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(raw_data))
        raw_array = np.array(img)
        print(f"  TIFF parsed: shape={raw_array.shape}, dtype={raw_array.dtype}")
        print(f"  Raw value range: {raw_array.min()} to {raw_array.max()}")

        temp_array = raw_to_temperature_flir_from_array(raw_array, metadata)

    except ImportError:
        print("  Warning: PIL not available, using manual parsing (less reliable)")
        temp_array = raw_to_temperature_flir(raw_data, width, height, metadata)
    except Exception as e:
        print(f"  PIL parsing failed: {e}, falling back to manual parsing")
        temp_array = raw_to_temperature_flir(raw_data, width, height, metadata)

    if temp_array is None:
        print("\nFailed to extract thermal data.")
        print("This image may not be a standard FLIR radiometric JPEG.")
        sys.exit(1)

    # Calculate statistics
    # Filter out error values (< -200°C or > 500°C are likely errors)
    valid_temps = temp_array[(temp_array > -200) & (temp_array < 500)]

    if len(valid_temps) == 0:
        print("\nError: No valid temperature values found.")
        print("The FLIR formula may not be compatible with this thermal camera.")
        sys.exit(1)

    min_temp = np.min(valid_temps)
    max_temp = np.max(valid_temps)
    avg_temp = np.mean(valid_temps)

    print(f"\nTemperature statistics:")
    print(f"  Min: {min_temp:.2f}°C")
    print(f"  Max: {max_temp:.2f}°C")
    print(f"  Average: {avg_temp:.2f}°C")
    print(f"  Range: {max_temp - min_temp:.2f}°C")

    # Save results
    base_name = image_path.stem

    # Save metadata JSON
    json_file = output_dir / f"{base_name}_thermal_data.json"
    output_data = {
        'width': width,
        'height': height,
        'metadata': {
            'camera': metadata.get('Model', 'Unknown'),
            'emissivity': metadata.get('Emissivity', 0.95),
            'distance': metadata.get('ObjectDistance', 0),
            'humidity': metadata.get('RelativeHumidity', 50),
            'atmospheric_temp': metadata.get('AtmosphericTemperature', 20),
            'planck_r1': metadata.get('PlanckR1', 0),
            'planck_b': metadata.get('PlanckB', 0),
            'planck_f': metadata.get('PlanckF', 0)
        },
        'statistics': {
            'min': float(min_temp),
            'max': float(max_temp),
            'average': float(avg_temp),
            'range': float(max_temp - min_temp)
        }
    }

    with open(json_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"\nMetadata saved to: {json_file}")

    # Save CSV
    csv_file = output_dir / f"{base_name}_thermal_data.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['x', 'y', 'temperature_celsius'])

        for y in range(height):
            for x in range(width):
                temp = temp_array[y, x]
                writer.writerow([x, y, f'{temp:.2f}'])

    print(f"CSV data saved to: {csv_file}")
    print("\nExtraction complete!")

if __name__ == '__main__':
    main()
