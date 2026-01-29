#!/usr/bin/env python3
"""
Quick tool to get temperature at specific pixels and calculate differences.
"""

import sys
import csv
import numpy as np

def load_thermal_data(csv_file):
    """Load thermal data into 2D array."""
    temps = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            temps.append(float(row['temperature_celsius']))

    return np.array(temps).reshape(1024, 1280)  # height x width

def get_temp_at_pixel(temp_array, x, y):
    """Get temperature at specific pixel coordinates."""
    if 0 <= x < 1280 and 0 <= y < 1024:
        return temp_array[y, x]
    else:
        print(f"Error: Pixel ({x}, {y}) out of bounds!")
        print("Valid range: x: 0-1279, y: 0-1023")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python get_pixel_temp.py <csv_file> <x> <y>")
        print("  python get_pixel_temp.py <csv_file> <x1> <y1> <x2> <y2>")
        print("\nExamples:")
        print("  python get_pixel_temp.py thermal.csv 640 512")
        print("  python get_pixel_temp.py thermal.csv 100 100 600 500")
        sys.exit(1)

    csv_file = sys.argv[1]
    temp_array = load_thermal_data(csv_file)

    if len(sys.argv) == 4:
        # Single pixel
        x = int(sys.argv[2])
        y = int(sys.argv[3])
        temp = get_temp_at_pixel(temp_array, x, y)
        if temp is not None:
            print(f"Temperature at pixel ({x}, {y}): {temp:.2f}°C")

    elif len(sys.argv) == 6:
        # Two pixels - calculate difference
        x1, y1 = int(sys.argv[2]), int(sys.argv[3])
        x2, y2 = int(sys.argv[4]), int(sys.argv[5])

        temp1 = get_temp_at_pixel(temp_array, x1, y1)
        temp2 = get_temp_at_pixel(temp_array, x2, y2)

        if temp1 is not None and temp2 is not None:
            diff = temp2 - temp1
            print(f"Pixel 1 ({x1}, {y1}): {temp1:.2f}°C")
            print(f"Pixel 2 ({x2}, {y2}): {temp2:.2f}°C")
            print(f"Temperature difference: {diff:.2f}°C")
            print(f"Absolute difference: {abs(diff):.2f}°C")
    else:
        print("Error: Invalid number of arguments")
        print("Use 4 args for single pixel, or 6 args for two pixels")

if __name__ == '__main__':
    main()
