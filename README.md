# Thermal Data Extraction Tool

Extract temperature data from drone thermal images (DJI and FLIR-based cameras).

## Supported Drones

### Fully Supported (DJI)
- DJI Mavic 3 Thermal (M3T)
- DJI Mavic 2 Enterprise Advanced (M2EA)
- DJI Matrice 30T (M30T)
- DJI Matrice 300 RTK with Zenmuse H20T/H20N
- All DJI drones with thermal cameras producing R-JPEG files

### Experimental Support (FLIR-based)
- Skydio X10 with VT300-Z sensor (FLIR Boson+)
- Autel EVO II Dual 640T
- Yuneec H520E with E10T/E20T
- Parrot Anafi USA/Thermal
- Any drone with FLIR thermal sensors (Boson, Lepton, Tau)

## Features

- Extract raw temperature data from thermal images
- Export to CSV format (x, y, temperature)
- Export metadata to JSON
- Generate thermal heatmaps
- Calculate temperature differences between pixels
- No data loss - direct sensor readings

## Installation

### Prerequisites

**For DJI images:**
- Docker (required - no alternatives available)
- DJI uses proprietary format that requires official SDK via Docker
- macOS, Windows, and Linux all need Docker

**For FLIR/Skydio images:**
- Python 3.7+
- exiftool
- Python packages: numpy, matplotlib, pillow
- No Docker needed

### Setup

1. Install Docker Desktop (for DJI images)

2. Install exiftool:
```bash
brew install exiftool  # macOS
# or
sudo apt-get install exiftool  # Linux
```

3. Install Python dependencies:
```bash
pip3 install numpy matplotlib pillow
```

4. Build Docker image (for DJI):
```bash
docker build -t dji-thermal-extractor .
```

## Quick Start

### Extract from DJI Image

```bash
# Place your DJI thermal image in the data folder
mkdir -p data/output

# Extract thermal data
docker run --rm \
  -v "$(pwd)/data:/data" \
  dji-thermal-extractor \
  node extract_thermal.js /data/YOUR_DJI_IMAGE.JPG /data/output
```

### Extract from Skydio/FLIR Image

```bash
# Place your thermal image in the data folder
mkdir -p data/output

# Extract thermal data
python3 extract_flir_thermal.py data/YOUR_IMAGE.JPG data/output
```

## Output Files

For each image, you get:

1. **CSV file** (`*_thermal_data.csv`)
   - Format: x, y, temperature_celsius
   - One row per pixel
   - Ready for Excel, Python, MATLAB

2. **JSON file** (`*_thermal_data.json`)
   - Image dimensions
   - Thermal parameters (emissivity, distance, humidity)
   - Temperature statistics (min, max, average)

## Analyze Thermal Data

### Generate Heatmaps and Statistics

```bash
python3 analyze_thermal.py data/output/thermal_data.csv data/output
```

Output:
- Thermal heatmap (PNG)
- Temperature profile graph (PNG)
- Statistics printed to console

### Get Temperature at Specific Pixels

```bash
# Single pixel
python3 get_pixel_temp.py data/output/thermal_data.csv 320 256

# Compare two pixels
python3 get_pixel_temp.py data/output/thermal_data.csv 100 100 600 500
```

### Solar Panel Inspection

Automatically detect defective solar panel cells:

```bash
python3 solar_panel_inspection.py data/output/thermal_data.csv data/output
```

Output:
- Segments panels from vegetation
- Identifies problem areas (defective cells)
- Draws red boxes around hotspots
- Exports detailed report with locations

## Usage Examples

### Solar Panel Inspection

```bash
# Extract thermal data
python3 extract_flir_thermal.py data/solar_panel.jpg data/output

# Analyze and create visualizations
python3 analyze_thermal.py data/output/solar_panel_thermal_data.csv data/output

# Find hot spots (anomalies)
# Check the heatmap: data/output/solar_panel_heatmap.png
```

### Building Thermal Survey

```bash
# Extract from DJI drone
docker run --rm \
  -v "$(pwd)/data:/data" \
  dji-thermal-extractor \
  node extract_thermal.js /data/building.jpg /data/output

# Get temperature at specific window
python3 get_pixel_temp.py data/output/building_thermal_data.csv 450 320
```

### Batch Processing

```bash
# Process all DJI images in a folder
for img in data/*.JPG; do
  docker run --rm \
    -v "$(pwd)/data:/data" \
    dji-thermal-extractor \
    node extract_thermal.js "/data/$(basename "$img")" /data/output
done

# Process all FLIR/Skydio images
for img in data/*.JPG; do
  python3 extract_flir_thermal.py "$img" data/output
done
```

## Verification

The extraction uses official SDKs and proven formulas:

**DJI images:**
- Official DJI Thermal SDK
- Conversion: Raw value / 10 = Temperature (°C)
- Accuracy: ±2°C or ±2% (per DJI specifications)

**FLIR images:**
- Standard FLIR Planck formula
- Uses camera calibration constants from image metadata
- Accuracy depends on camera model (typically ±2-3°C)

To verify:
1. Open image in manufacturer software (DJI Thermal Analysis Tool, FLIR Tools)
2. Click on a pixel
3. Compare with extracted CSV data - should match exactly

## Troubleshooting

### "Failed to create DIRP handle"
Your image is not a DJI format. Try FLIR extraction:
```bash
python3 extract_flir_thermal.py data/image.jpg data/output
```

### "Docker is not running"
Start Docker Desktop application before running extraction.

### Temperature values seem wrong
Check that:
1. Image is radiometric (R-JPEG), not visual-only
2. Camera thermal mode was enabled during capture
3. You're using the correct extraction method (DJI vs FLIR)

### Some pixels show extreme values
For FLIR images, a small number of edge pixels (<1%) may have errors. This is normal and doesn't affect the rest of the data.

## Technical Details

### DJI Format
- Format: Proprietary R-JPEG with DIRP thermal data
- Raw values stored as uint16
- Temperature (°C) = Raw Value / 10

### FLIR Format
- Format: Standard R-JPEG with embedded TIFF thermal data
- Uses Planck's radiation formula for conversion
- Formula: T = B / ln(R1 / (R2 * (raw + O)) + F) - 273.15
- Constants (R1, R2, B, F, O) stored in image EXIF metadata

## File Structure

```
.
├── README.md                    # This file
├── Dockerfile                   # Docker setup for DJI extraction
├── package.json                 # Node.js dependencies
├── extract_thermal.js           # DJI extraction script (runs in Docker)
├── extract_flir_thermal.py      # FLIR/Skydio extraction script
├── analyze_thermal.py           # Analysis and visualization tool
├── get_pixel_temp.py            # Quick pixel temperature lookup
├── data/                        # Input images go here
│   └── output/                  # Extracted data saved here
└── .dockerignore               # Docker ignore file
```

## Python API

### Load Thermal Data

```python
import csv
import numpy as np

# Load from CSV
temperatures = []
with open('thermal_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        temperatures.append(float(row['temperature_celsius']))

# Reshape to 2D array (height x width)
# For DJI M3T: 1280 x 1024
# For Skydio X10: 640 x 512
temp_array = np.array(temperatures).reshape(height, width)

# Get temperature at pixel (x, y)
temp = temp_array[y, x]  # Note: y first, then x

# Calculate difference between two pixels
diff = temp_array[y2, x2] - temp_array[y1, x1]
```

## Contributing

This tool is provided as-is for thermal data extraction. Feel free to modify and share.

## License

Open source - use freely for any purpose.

## References

### DJI Thermal Extraction
- [DJI Thermal SDK](https://github.com/gmazoni/dji-thermal-sdk) - Official DJI thermal data extraction library

### FLIR Thermal Calculation Formula
The FLIR temperature conversion uses Planck's radiation law with factory calibration constants.

Official FLIR Documentation:
- [FLIR Temperature Measurement Formula](https://flir.custhelp.com/app/answers/detail/a_id/3321/) - Official formula documentation
- [FLIR Radiometric JPEG Format](https://flir.custhelp.com/app/answers/detail/a_id/1729/) - R-JPEG specification
- [FLIR UAS Radiometric Tech Note](https://flir.custhelp.com/ci/fattach/get/107853/0/filename/suas-radiometric-tech-note-en.pdf) - Technical documentation for drone cameras

Open Source Implementations:
- [Thermimage R Package](https://cran.r-project.org/web/packages/Thermimage/Thermimage.pdf) - Academic research implementation
- [flirpy Python Library](https://flirpy.readthedocs.io/en/latest/getting_started/cameras.html) - Python thermal imaging library

Formula: `T = B / ln(R1 / (R2 × (raw + O)) + F) - 273.15`

Where R1, R2, B, F, O are Planck calibration constants stored in image EXIF metadata.

## Credits

- DJI Thermal SDK by gmazoni
- FLIR Planck formula from official FLIR documentation
- Built with Node.js, Python, Docker

## Support

For issues or questions about specific drone models, check the manufacturer documentation:
- DJI: https://www.dji.com/support
- FLIR: https://www.flir.com/support
- Skydio: https://support.skydio.com
