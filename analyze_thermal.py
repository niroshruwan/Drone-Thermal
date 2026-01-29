#!/usr/bin/env python3
"""
Thermal Data Analysis Tool

Analyzes extracted thermal data from CSV files.
Works with both DJI and FLIR/Skydio thermal images.

Usage:
    python3 analyze_thermal.py <csv_file> [output_dir]

Example:
    python3 analyze_thermal.py data/output/thermal_data.csv data/output
"""

import sys
import csv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def load_thermal_csv(csv_file):
    """
    Load thermal data from CSV file into a 2D numpy array.

    Args:
        csv_file: Path to CSV file with columns: x, y, temperature_celsius

    Returns:
        numpy array of shape (height, width) with temperature values
    """
    print(f"Loading thermal data from {csv_file}...")

    temperatures = []
    max_x = 0
    max_y = 0

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            temperatures.append(float(row['temperature_celsius']))
            max_x = max(max_x, int(row['x']))
            max_y = max(max_y, int(row['y']))

    # Dimensions are max + 1 (since indices start at 0)
    width = max_x + 1
    height = max_y + 1

    # Reshape into 2D array
    temp_array = np.array(temperatures).reshape(height, width)

    print(f"Loaded {len(temperatures)} temperature values")
    print(f"Image dimensions: {width} x {height}")

    return temp_array


def analyze_thermal_data(temp_array):
    """
    Calculate and print thermal statistics.

    Args:
        temp_array: 2D numpy array of temperatures
    """
    # Filter out error values (< -200C are errors)
    valid_temps = temp_array[temp_array > -200]

    total_pixels = temp_array.size
    valid_pixels = valid_temps.size
    error_pixels = total_pixels - valid_pixels

    print(f"\n{'='*60}")
    print("OVERALL STATISTICS")
    print(f"{'='*60}")
    print(f"Total pixels: {total_pixels:,}")
    print(f"Valid pixels: {valid_pixels:,}")
    print(f"Error pixels: {error_pixels:,}")
    print(f"Min temperature: {np.min(valid_temps):.2f} C")
    print(f"Max temperature: {np.max(valid_temps):.2f} C")
    print(f"Mean temperature: {np.mean(valid_temps):.2f} C")
    print(f"Std deviation: {np.std(valid_temps):.2f} C")
    print(f"Temperature range: {np.max(valid_temps) - np.min(valid_temps):.2f} C")

    # Find hot and cold spots
    hot_threshold = np.percentile(valid_temps, 95)
    cold_threshold = np.percentile(valid_temps, 5)

    print(f"\n{'='*60}")
    print("HOT AND COLD SPOTS")
    print(f"{'='*60}")

    print(f"\nHot Spots (top 5% warmest):")
    print(f"  Threshold: {hot_threshold:.2f} C")
    print(f"  Number of hot pixels: {np.sum(valid_temps >= hot_threshold):,}")

    # Find hottest pixel location
    max_idx = np.unravel_index(np.argmax(temp_array), temp_array.shape)
    print(f"  Hottest pixel: ({max_idx[1]}, {max_idx[0]}) at {temp_array[max_idx]:.2f} C")

    print(f"\nCold Spots (bottom 5% coldest):")
    print(f"  Threshold: {cold_threshold:.2f} C")
    print(f"  Number of cold pixels: {np.sum(valid_temps <= cold_threshold):,}")

    # Find coldest valid pixel location
    min_val = valid_temps.min()
    min_idx = np.where(temp_array == min_val)
    min_y, min_x = min_idx[0][0], min_idx[1][0]
    print(f"  Coldest pixel: ({min_x}, {min_y}) at {min_val:.2f} C")


def create_thermal_heatmap(temp_array, output_file):
    """
    Create a thermal heatmap visualization.

    Args:
        temp_array: 2D numpy array of temperatures
        output_file: Path to save the heatmap image
    """
    # Mask error values for visualization
    masked_array = np.ma.masked_where(temp_array < -200, temp_array)

    plt.figure(figsize=(14, 10))

    # Create heatmap with jet colormap (blue=cold, red=hot)
    im = plt.imshow(masked_array, cmap='jet', aspect='auto', interpolation='nearest')

    # Add colorbar
    cbar = plt.colorbar(im, label='Temperature (C)')

    # Title and labels
    height, width = temp_array.shape
    plt.title(f'Thermal Heatmap ({width}x{height})', fontsize=14, fontweight='bold')
    plt.xlabel('X (pixels)', fontsize=12)
    plt.ylabel('Y (pixels)', fontsize=12)

    # Add statistics box
    valid_temps = temp_array[temp_array > -200]
    stats_text = f'Min: {valid_temps.min():.1f}C\nMax: {valid_temps.max():.1f}C\nMean: {valid_temps.mean():.1f}C'
    plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
             verticalalignment='top', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nHeatmap saved to: {output_file}")
    plt.close()


def create_temperature_profile(temp_array, y_row, output_file):
    """
    Create a temperature profile graph along a horizontal line.

    Args:
        temp_array: 2D numpy array of temperatures
        y_row: Row number to extract profile from
        output_file: Path to save the profile graph
    """
    # Extract temperature profile at specified row
    profile = temp_array[y_row, :]

    # Filter valid values for statistics
    valid_profile = profile[profile > -200]

    plt.figure(figsize=(14, 6))

    # Plot temperature profile
    x_values = np.arange(len(profile))
    plt.plot(x_values, profile, linewidth=1, color='royalblue')

    # Add statistical reference lines
    if len(valid_profile) > 0:
        plt.axhline(y=valid_profile.mean(), color='red', linestyle='--',
                   linewidth=2, label=f'Mean: {valid_profile.mean():.2f}C', alpha=0.7)
        plt.axhline(y=valid_profile.max(), color='orange', linestyle='--',
                   linewidth=1.5, label=f'Max: {valid_profile.max():.2f}C', alpha=0.5)
        plt.axhline(y=valid_profile.min(), color='blue', linestyle='--',
                   linewidth=1.5, label=f'Min: {valid_profile.min():.2f}C', alpha=0.5)

    # Labels and title
    plt.title(f'Temperature Profile at Row Y={y_row}', fontsize=14, fontweight='bold')
    plt.xlabel('X (pixels)', fontsize=12)
    plt.ylabel('Temperature (C)', fontsize=12)
    plt.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    plt.legend(loc='best', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Temperature profile saved to: {output_file}")
    plt.close()


def main():
    """Main function to analyze thermal data."""
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_thermal.py <csv_file> [output_dir]")
        print("Example: python3 analyze_thermal.py data/output/thermal_data.csv data/output")
        sys.exit(1)

    csv_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else csv_file.parent)

    # Validate input
    if not csv_file.exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load thermal data
    temp_array = load_thermal_csv(csv_file)

    # Analyze and print statistics
    analyze_thermal_data(temp_array)

    # Create visualizations
    print(f"\n{'='*60}")
    print("CREATING VISUALIZATIONS")
    print(f"{'='*60}")

    base_name = csv_file.stem.replace('_thermal_data', '')
    height, width = temp_array.shape

    # Generate heatmap
    heatmap_file = output_dir / f"{base_name}_heatmap.png"
    create_thermal_heatmap(temp_array, heatmap_file)

    # Generate temperature profile at center row
    profile_file = output_dir / f"{base_name}_profile.png"
    create_temperature_profile(temp_array, height // 2, profile_file)

    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print("\nTo get temperature at specific pixels:")
    print("  python3 get_pixel_temp.py <csv_file> <x> <y>")
    print("\nTo calculate temperature difference:")
    print("  python3 get_pixel_temp.py <csv_file> <x1> <y1> <x2> <y2>")


if __name__ == '__main__':
    main()
