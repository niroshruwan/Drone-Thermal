#!/usr/bin/env python3
"""
Solar Panel Thermal Inspection Tool - Simple and Accurate

Automatically finds defective solar panel areas from thermal images.
Uses two-stage segmentation:
1. Find uniform panel areas (vs random vegetation)
2. Find hot regions within panels (top 5% warmest)

No manual tuning needed - just run it.

Usage:
    python3 solar_panel_inspection_v2.py <csv_file> [output_dir]

Example:
    python3 solar_panel_inspection_v2.py data/output/thermal_data.csv data/output
"""

import sys
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import ListedColormap
from scipy import ndimage
from pathlib import Path
import json


def load_thermal_csv(csv_file):
    """Load thermal data from CSV file."""
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

    width = max_x + 1
    height = max_y + 1
    temp_array = np.array(temperatures).reshape(height, width)

    print(f"Image dimensions: {width}x{height}\n")
    return temp_array


def segment_panels(temp_array):
    """
    Segment solar panels from vegetation.

    Step 1: Find uniform areas (Segment 1)
    Step 2: Filter to cooler panel strips (exclude hot vegetation)
    """
    print("Segmenting panels from vegetation...")

    # Find uniform areas (low local variance)
    local_std = ndimage.generic_filter(temp_array, np.std, size=15)
    std_threshold = np.median(local_std)
    uniform_areas = local_std < std_threshold

    print(f"  Uniform areas (Segment 1): {np.sum(uniform_areas):,} pixels")

    # Label continuous regions in uniform areas
    labeled, num_regions = ndimage.label(uniform_areas)

    # Keep only large regions with panel-like temperatures (<50°C average)
    panel_mask = np.zeros_like(temp_array, dtype=bool)

    for region_id in range(1, num_regions + 1):
        region_mask = (labeled == region_id)
        region_size = np.sum(region_mask)

        if region_size < 1000:
            continue

        region_avg = np.mean(temp_array[region_mask])

        if region_avg < 50.0:  # Panel strips
            panel_mask |= region_mask

    print(f"  Panel areas: {np.sum(panel_mask):,} pixels ({np.sum(panel_mask)/panel_mask.size*100:.1f}%)\n")

    return panel_mask


def find_problem_areas(temp_array, panel_mask):
    """
    Find distinct problem areas in panels.
    Uses top 5% hottest panel pixels with aggressive merging.
    """
    print("Finding problem areas...")

    panel_temps = temp_array[panel_mask]
    panel_median = np.median(panel_temps)

    # Find top 5% hottest pixels in panels
    temp_95 = np.percentile(panel_temps, 95)

    hotspots = (temp_array >= temp_95) & panel_mask

    print(f"  Panel median: {panel_median:.2f}°C")
    print(f"  Hotspot threshold (top 5%): {temp_95:.2f}°C")
    print(f"  Raw hotspot pixels: {np.sum(hotspots):,}")

    # Very aggressive merging to group into distinct problem areas
    # Dilation connects hotspots within ~70 pixels of each other
    hotspots = ndimage.binary_dilation(hotspots, iterations=35)
    hotspots = ndimage.binary_erosion(hotspots, iterations=33)
    hotspots = ndimage.binary_fill_holes(hotspots)

    print(f"  After merging: {np.sum(hotspots):,} pixels")

    # Label distinct regions
    labeled, num_regions = ndimage.label(hotspots)

    # Get bounding boxes for each region
    problem_areas = []

    for region_id in range(1, num_regions + 1):
        region_mask = (labeled == region_id)
        size = np.sum(region_mask)

        # Filter by size - larger minimum for distinct areas
        if size < 150:
            continue

        # Get bounding box
        rows, cols = np.where(region_mask)
        x_min, x_max = cols.min(), cols.max()
        y_min, y_max = rows.min(), rows.max()

        # Get temperature stats
        region_temps = temp_array[region_mask]
        max_temp = float(np.max(region_temps))
        mean_temp = float(np.mean(region_temps))

        problem_areas.append({
            'id': region_id,
            'x_min': int(x_min),
            'y_min': int(y_min),
            'x_max': int(x_max),
            'y_max': int(y_max),
            'center_x': int((x_min + x_max) / 2),
            'center_y': int((y_min + y_max) / 2),
            'width': int(x_max - x_min + 1),
            'height': int(y_max - y_min + 1),
            'pixels': int(size),
            'max_temp': max_temp,
            'mean_temp': mean_temp,
            'delta': max_temp - panel_median
        })

    # Sort by severity (delta from median)
    problem_areas.sort(key=lambda x: x['delta'], reverse=True)

    print(f"\nProblem areas found: {len(problem_areas)}\n")

    return problem_areas, panel_median


def visualize_results(temp_array, panel_mask, problem_areas, output_file):
    """Create visualization with problem areas marked."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # Left: Panel segmentation
    segmentation = np.zeros_like(temp_array)
    segmentation[panel_mask] = 1

    colors = ['orange', 'blue']  # Orange=vegetation, Blue=panel
    cmap = ListedColormap(colors)
    im1 = ax1.imshow(segmentation, cmap=cmap, aspect='auto')
    ax1.set_title('Panel Segmentation\n(Blue=Panel, Orange=Vegetation)', fontsize=12, fontweight='bold')
    ax1.set_xlabel('X (pixels)')
    ax1.set_ylabel('Y (pixels)')

    # Right: Thermal image with problem areas marked
    im2 = ax2.imshow(temp_array, cmap='jet', aspect='auto')
    plt.colorbar(im2, ax=ax2, label='Temperature (°C)')
    ax2.set_title(f'Problem Areas Detected: {len(problem_areas)}', fontsize=12, fontweight='bold')
    ax2.set_xlabel('X (pixels)')
    ax2.set_ylabel('Y (pixels)')

    # Draw bounding boxes
    for area in problem_areas:
        rect = patches.Rectangle(
            (area['x_min'], area['y_min']),
            area['width'], area['height'],
            linewidth=3,
            edgecolor='red',
            facecolor='none'
        )
        ax2.add_patch(rect)

        # Add label
        label = f"#{area['id']}\n{area['max_temp']:.1f}°C"
        ax2.text(
            area['x_min'] + 5,
            area['y_min'] + 15,
            label,
            color='white',
            fontsize=10,
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='red', alpha=0.8)
        )

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Visualization saved to: {output_file}")
    plt.close()


def export_report(problem_areas, panel_median, output_file):
    """Export problem area report to JSON."""
    report = {
        'panel_median_temp': panel_median,
        'total_problem_areas': len(problem_areas),
        'problem_areas': problem_areas
    }

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {output_file}\n")

    # Print summary
    print("="*60)
    print(f"SOLAR PANEL INSPECTION SUMMARY")
    print("="*60)
    print(f"Panel median temperature: {panel_median:.2f}°C")
    print(f"Problem areas detected: {len(problem_areas)}\n")

    if len(problem_areas) > 0:
        print("Problem areas (sorted by severity):")
        for area in problem_areas[:10]:
            print(f"  #{area['id']}: Row {area['center_y']:3d}, "
                  f"{area['max_temp']:.2f}°C (+{area['delta']:.1f}°C), "
                  f"{area['pixels']} pixels")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 solar_panel_inspection_v2.py <csv_file> [output_dir]")
        print("Example: python3 solar_panel_inspection_v2.py data/output/thermal_data.csv data/output")
        sys.exit(1)

    csv_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else 'data/output')

    if not csv_file.exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    temp_array = load_thermal_csv(csv_file)

    # Segment panels
    panel_mask = segment_panels(temp_array)

    # Find problem areas
    problem_areas, panel_median = find_problem_areas(temp_array, panel_mask)

    # Create visualization
    base_name = csv_file.stem.replace('_thermal_data', '')
    viz_file = output_dir / f"{base_name}_inspection.png"
    visualize_results(temp_array, panel_mask, problem_areas, viz_file)

    # Export report
    report_file = output_dir / f"{base_name}_inspection_report.json"
    export_report(problem_areas, panel_median, report_file)

    print("\nInspection complete!")


if __name__ == '__main__':
    main()
