/**
 * DJI Thermal Data Extraction Script
 *
 * Extracts temperature data from DJI thermal camera R-JPEG images.
 * Uses the official DJI Thermal SDK.
 *
 * Usage: node extract_thermal.js <input_image> [output_directory]
 * Example: node extract_thermal.js /data/thermal.jpg /data/output
 */

const fs = require('fs');
const path = require('path');
const { getTemperatureData } = require('dji-thermal-sdk');

// Get input file from command line or use default
const inputFile = process.argv[2] || '/data/input.jpg';
const outputDir = process.argv[3] || '/data/output';

if (!fs.existsSync(inputFile)) {
  console.error(`Error: Input file not found: ${inputFile}`);
  console.log('\nUsage: node extract_thermal.js <input_image> [output_directory]');
  console.log('Example: node extract_thermal.js /data/thermal.jpg /data/output');
  process.exit(1);
}

// Create output directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

console.log(`Processing thermal image: ${inputFile}`);

// Read the image file
const imageBuffer = fs.readFileSync(inputFile);

try {
  // Extract thermal data
  const thermalData = getTemperatureData(imageBuffer);

  console.log(`\nImage dimensions: ${thermalData.width} x ${thermalData.height}`);
  console.log('Thermal parameters:');
  console.log(`  Distance: ${thermalData.parameters.distance}m`);
  console.log(`  Humidity: ${thermalData.parameters.humidity}%`);
  console.log(`  Emissivity: ${thermalData.parameters.emissivity}`);
  console.log(`  Reflection: ${thermalData.parameters.reflection}°C`);

  // Calculate statistics efficiently without creating full array
  let minTemp = Infinity;
  let maxTemp = -Infinity;
  let sum = 0;

  for (let i = 0; i < thermalData.data.length; i++) {
    const temp = thermalData.data[i] / 10;
    if (temp < minTemp) minTemp = temp;
    if (temp > maxTemp) maxTemp = temp;
    sum += temp;
  }

  const avgTemp = sum / thermalData.data.length;

  console.log(`\nTemperature statistics:`);
  console.log(`  Min: ${minTemp.toFixed(2)}°C`);
  console.log(`  Max: ${maxTemp.toFixed(2)}°C`);
  console.log(`  Average: ${avgTemp.toFixed(2)}°C`);

  // Save raw temperature data as JSON
  const baseName = path.basename(inputFile, path.extname(inputFile));
  const jsonOutput = path.join(outputDir, `${baseName}_thermal_data.json`);

  // Save metadata (without full temperature array to avoid memory issues)
  const output = {
    width: thermalData.width,
    height: thermalData.height,
    metadata: {
      distance: thermalData.parameters.distance,
      humidity: thermalData.parameters.humidity,
      emissivity: thermalData.parameters.emissivity,
      reflection: thermalData.parameters.reflection
    },
    statistics: {
      min: minTemp,
      max: maxTemp,
      average: avgTemp
    }
  };

  fs.writeFileSync(jsonOutput, JSON.stringify(output, null, 2));
  console.log(`\nMetadata saved to: ${jsonOutput}`);

  // Save as CSV for easy import into other tools (stream write for large files)
  const csvOutput = path.join(outputDir, `${baseName}_thermal_data.csv`);
  const csvStream = fs.createWriteStream(csvOutput);
  csvStream.write('x,y,temperature_celsius\n');

  for (let i = 0; i < thermalData.data.length; i++) {
    const x = i % thermalData.width;
    const y = Math.floor(i / thermalData.width);
    const temp = (thermalData.data[i] / 10).toFixed(2);
    csvStream.write(`${x},${y},${temp}\n`);
  }

  csvStream.end();
  console.log(`CSV data saved to: ${csvOutput}`);

  console.log('\nExtraction complete!');

} catch (error) {
  console.error('Error processing thermal image:', error.message);
  process.exit(1);
}
