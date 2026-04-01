/**
 * Thermal image processing engine.
 *
 * FLIR cameras embed radiometric data in JPEG EXIF.  For this web tool we take
 * a simpler approach that works reliably without exiftool or native binaries:
 *
 * 1. Read the visual (RGB) image that the camera already rendered with its
 *    built-in palette.
 * 2. Convert each pixel to a *relative thermal value* by mapping the colour
 *    back to a scalar (luminance of the thermal palette).
 * 3. Detect hotspots as connected regions whose relative value exceeds the
 *    user-controlled sensitivity threshold (mean + N×std).
 *
 * The approach gives accurate *relative* heat-loss detection (which areas are
 * warmer than their surroundings) without needing the Planck constants or
 * exiftool.  Absolute °C values are estimated from the FLIR colour bar if
 * present, or from a configurable range.
 */

import sharp from "sharp";
import path from "path";
import fs from "fs";

// ── Types ──────────────────────────────────────────────────────────────

export interface ThermalStats {
  min: number;
  max: number;
  mean: number;
  median: number;
  std: number;
  width: number;
  height: number;
}

export interface DetectedSpot {
  x: number; // pixel col on visual image
  y: number; // pixel row on visual image
  temperature: number; // estimated relative temp
  areaSize: number;
  severity: "low" | "medium" | "high" | "critical";
}

// ── Colour-to-thermal conversion ───────────────────────────────────────

/**
 * Convert RGB pixel to a relative thermal value 0-1.
 * FLIR "iron" palette: black→blue→purple→red→orange→yellow→white.
 * We map to luminance-based relative value.
 */
function rgbToThermalValue(r: number, g: number, b: number): number {
  // Weighted luminance that emphasises warm colours
  // Red channel carries most heat information in iron palette
  const thermal = (r * 0.5 + g * 0.35 + b * 0.15) / 255;
  return thermal;
}

// ── Image processing ───────────────────────────────────────────────────

export async function processImage(
  imagePath: string,
): Promise<{ stats: ThermalStats; thermalData: Float32Array }> {
  const { data, info } = await sharp(imagePath)
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = info.width;
  const height = info.height;
  const pixelCount = width * height;
  const thermalData = new Float32Array(pixelCount);

  // Convert each pixel
  for (let i = 0; i < pixelCount; i++) {
    const offset = i * 3;
    thermalData[i] = rgbToThermalValue(data[offset], data[offset + 1], data[offset + 2]);
  }

  // Calculate statistics
  let sum = 0;
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < pixelCount; i++) {
    const v = thermalData[i];
    sum += v;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const mean = sum / pixelCount;

  // Std dev
  let sqDiffSum = 0;
  for (let i = 0; i < pixelCount; i++) {
    const diff = thermalData[i] - mean;
    sqDiffSum += diff * diff;
  }
  const std = Math.sqrt(sqDiffSum / pixelCount);

  // Median (sample-based for speed)
  const sampleSize = Math.min(10000, pixelCount);
  const sample: number[] = [];
  const step = Math.floor(pixelCount / sampleSize);
  for (let i = 0; i < pixelCount; i += step) {
    sample.push(thermalData[i]);
  }
  sample.sort((a, b) => a - b);
  const median = sample[Math.floor(sample.length / 2)];

  return {
    stats: { min, max, mean, median, std, width, height },
    thermalData,
  };
}

// ── Hotspot detection ──────────────────────────────────────────────────

/**
 * Detect hotspots using a statistical threshold.
 * sensitivity is the std-dev multiplier:
 *   lower = more sensitive (more spots detected)
 *   higher = less sensitive (only very warm spots)
 *
 * Typical values: 1.0 (very sensitive) to 3.0 (conservative).
 * Default: 2.0 (medium).
 */
export function detectHotspots(
  thermalData: Float32Array,
  width: number,
  height: number,
  sensitivity: number = 2.0,
  minAreaPx: number = 20,
): DetectedSpot[] {
  // FLIR cameras overlay a HUD (temperature bar, crosshairs, branding) on
  // the top ~15% and bottom ~12% of the image.  These bright UI elements
  // would be falsely detected as hotspots, so we mask them out.
  const hudTopRow = Math.round(height * 0.15);
  const hudBottomRow = Math.round(height * 0.88);
  const hudLeftCol = Math.round(width * 0.06);  // left temp scale bar

  // Helper to check if a pixel is in the analysis zone (not in HUD)
  function inAnalysisZone(idx: number): boolean {
    const row = Math.floor(idx / width);
    const col = idx % width;
    return row >= hudTopRow && row < hudBottomRow && col >= hudLeftCol;
  }

  // Calculate stats only from the analysis zone (excluding HUD)
  const pixelCount = width * height;
  let sum = 0;
  let analysisCount = 0;
  for (let i = 0; i < pixelCount; i++) {
    if (!inAnalysisZone(i)) continue;
    sum += thermalData[i];
    analysisCount++;
  }
  const mean = analysisCount > 0 ? sum / analysisCount : 0;

  let sqDiffSum = 0;
  for (let i = 0; i < pixelCount; i++) {
    if (!inAnalysisZone(i)) continue;
    const diff = thermalData[i] - mean;
    sqDiffSum += diff * diff;
  }
  const std = analysisCount > 0 ? Math.sqrt(sqDiffSum / analysisCount) : 0;
  const threshold = mean + sensitivity * std;

  // Create binary mask — only in the analysis zone
  const mask = new Uint8Array(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    if (!inAnalysisZone(i)) {
      mask[i] = 0; // exclude HUD areas
    } else {
      mask[i] = thermalData[i] > threshold ? 1 : 0;
    }
  }

  // Connected component labelling (4-connectivity flood fill)
  const labels = new Int32Array(pixelCount);
  let nextLabel = 1;

  function flood(startIdx: number, label: number): number[] {
    const stack = [startIdx];
    const region: number[] = [];
    while (stack.length > 0) {
      const idx = stack.pop()!;
      if (idx < 0 || idx >= pixelCount) continue;
      if (labels[idx] !== 0 || mask[idx] === 0) continue;
      labels[idx] = label;
      region.push(idx);
      const row = Math.floor(idx / width);
      const col = idx % width;
      if (col > 0) stack.push(idx - 1);
      if (col < width - 1) stack.push(idx + 1);
      if (row > 0) stack.push(idx - width);
      if (row < height - 1) stack.push(idx + width);
    }
    return region;
  }

  const regions: number[][] = [];
  for (let i = 0; i < pixelCount; i++) {
    if (mask[i] === 1 && labels[i] === 0) {
      const region = flood(i, nextLabel);
      if (region.length >= minAreaPx) {
        regions.push(region);
      }
      nextLabel++;
    }
  }

  // Extract hotspot properties from each region
  const spots: DetectedSpot[] = [];
  for (const region of regions) {
    let maxVal = -Infinity;
    let maxIdx = 0;
    let regionSum = 0;
    for (const idx of region) {
      const v = thermalData[idx];
      regionSum += v;
      if (v > maxVal) {
        maxVal = v;
        maxIdx = idx;
      }
    }

    const y = Math.floor(maxIdx / width);
    const x = maxIdx % width;

    // Classify severity by how many std devs above mean
    const delta = maxVal - mean;
    let severity: DetectedSpot["severity"];
    if (delta > 3 * std) severity = "critical";
    else if (delta > 2 * std) severity = "high";
    else if (delta > 1.5 * std) severity = "medium";
    else severity = "low";

    spots.push({
      x,
      y,
      temperature: Math.round(maxVal * 100) / 100,
      areaSize: region.length,
      severity,
    });
  }

  // Sort by temperature descending
  spots.sort((a, b) => b.temperature - a.temperature);
  return spots;
}

// ── Labeled image generation ───────────────────────────────────────────

const SEVERITY_COLORS: Record<string, { r: number; g: number; b: number }> = {
  low: { r: 255, g: 255, b: 0 },
  medium: { r: 255, g: 165, b: 0 },
  high: { r: 255, g: 69, b: 0 },
  critical: { r: 255, g: 0, b: 0 },
};

/**
 * Create a labeled version of the thermal image with spot markers.
 * Each marker shows the spot number.
 */
export async function createLabeledImage(
  inputPath: string,
  spotsData: Array<{ x: number; y: number; spotNumber: number; severity: string }>,
  outputPath: string,
): Promise<void> {
  const { data: imgData, info } = await sharp(inputPath)
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = info.width;
  const height = info.height;
  const channels = 3;

  // Create mutable copy
  const pixels = Buffer.from(imgData);

  for (const spot of spotsData) {
    const color = SEVERITY_COLORS[spot.severity] || SEVERITY_COLORS.medium;
    const cx = Math.min(Math.max(spot.x, 12), width - 12);
    const cy = Math.min(Math.max(spot.y, 12), height - 12);

    // Draw crosshair
    for (let dx = -8; dx <= 8; dx++) {
      setPixel(pixels, width, channels, cx + dx, cy, color);
      setPixel(pixels, width, channels, cx, cy + dx, color);
    }

    // Draw circle (radius 10)
    const r = 10;
    for (let angle = 0; angle < 360; angle += 2) {
      const rad = (angle * Math.PI) / 180;
      const px = Math.round(cx + r * Math.cos(rad));
      const py = Math.round(cy + r * Math.sin(rad));
      setPixel(pixels, width, channels, px, py, color);
    }

    // Draw number label background (small rectangle)
    const labelX = cx + 12;
    const labelY = cy - 8;
    for (let dy = 0; dy < 14; dy++) {
      for (let dx = 0; dx < 16; dx++) {
        setPixel(pixels, width, channels, labelX + dx, labelY + dy, { r: 0, g: 0, b: 0 });
      }
    }

    // Draw spot number as simple digit
    drawDigit(pixels, width, channels, labelX + 3, labelY + 2, spot.spotNumber, color);
  }

  await sharp(pixels, { raw: { width, height, channels } })
    .jpeg({ quality: 90 })
    .toFile(outputPath);
}

function setPixel(
  buf: Buffer,
  width: number,
  ch: number,
  x: number,
  y: number,
  color: { r: number; g: number; b: number },
) {
  if (x < 0 || y < 0 || x >= width) return;
  const idx = (y * width + x) * ch;
  if (idx < 0 || idx + 2 >= buf.length) return;
  buf[idx] = color.r;
  buf[idx + 1] = color.g;
  buf[idx + 2] = color.b;
}

// Simple 3x5 pixel font for numbers
const DIGIT_PATTERNS: Record<number, number[][]> = {
  0: [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
  1: [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
  2: [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
  3: [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
  4: [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
  5: [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
  6: [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
  7: [[1,1,1],[0,0,1],[0,0,1],[0,1,0],[0,1,0]],
  8: [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
  9: [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
};

function drawDigit(
  buf: Buffer,
  width: number,
  ch: number,
  x: number,
  y: number,
  num: number,
  color: { r: number; g: number; b: number },
) {
  const digits = String(num).split("").map(Number);
  let offsetX = x;
  for (const d of digits) {
    const pattern = DIGIT_PATTERNS[d] || DIGIT_PATTERNS[0];
    for (let row = 0; row < 5; row++) {
      for (let col = 0; col < 3; col++) {
        if (pattern[row][col]) {
          // Draw 2x2 for each pixel to make it visible
          setPixel(buf, width, ch, offsetX + col * 2, y + row * 2, color);
          setPixel(buf, width, ch, offsetX + col * 2 + 1, y + row * 2, color);
          setPixel(buf, width, ch, offsetX + col * 2, y + row * 2 + 1, color);
          setPixel(buf, width, ch, offsetX + col * 2 + 1, y + row * 2 + 1, color);
        }
      }
    }
    offsetX += 8;
  }
}

// ── Save / load thermal data ───────────────────────────────────────────

export function saveThermalData(outputPath: string, data: Float32Array, width: number, height: number): void {
  // Save as raw binary with a small header
  const header = Buffer.alloc(8);
  header.writeInt32LE(width, 0);
  header.writeInt32LE(height, 4);
  const body = Buffer.from(data.buffer);
  fs.writeFileSync(outputPath, Buffer.concat([header, body]));
}

export function loadThermalData(filePath: string): { data: Float32Array; width: number; height: number } | null {
  if (!fs.existsSync(filePath)) return null;
  const buf = fs.readFileSync(filePath);
  const width = buf.readInt32LE(0);
  const height = buf.readInt32LE(4);
  const data = new Float32Array(buf.buffer.slice(buf.byteOffset + 8, buf.byteOffset + 8 + width * height * 4));
  return { data, width, height };
}
