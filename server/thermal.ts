/**
 * Thermal image processing engine.
 *
 * Raw thermal data is extracted from FLIR radiometric JPEGs using
 * flirimageextractor (Python) via a subprocess call to flir_extract.py.
 * This gives actual per-pixel °C values from the EXIF data — the FLIR
 * HUD (logo, temperature bar, crosshairs) is absent from the raw array,
 * so it cannot cause false-positive hotspot detections.
 */

import { execFile } from "child_process";
import { promisify } from "util";
import sharp from "sharp";
import path from "path";
import fs from "fs";

const execFileAsync = promisify(execFile);

// Resolve the Python bridge script relative to this file
const FLIR_EXTRACT_SCRIPT = path.join(path.dirname(new URL(import.meta.url).pathname), "flir_extract.py");

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
  x: number;        // pixel col on visual image
  y: number;        // pixel row on visual image
  temperature: number;  // degrees C (raw radiometric value)
  areaSize: number;
  severity: "low" | "medium" | "high" | "critical";
}

// ── Image processing ───────────────────────────────────────────────────

/**
 * Extract raw thermal data from a FLIR radiometric JPEG.
 *
 * Calls flir_extract.py which uses flirimageextractor + exiftool to read
 * the embedded Planck-equation thermal data directly from EXIF — the same
 * approach used by the Flask version of this app.  Returns a Float32Array
 * of raw °C values, row-major, plus stats.
 *
 * Falls back to the legacy RGB-luminance method if the Python extractor
 * fails (e.g. non-FLIR JPEG uploaded for testing), with a console warning.
 */
export async function processImage(
  imagePath: string,
): Promise<{ stats: ThermalStats; thermalData: Float32Array }> {
  try {
    return await extractViaFlirTool(imagePath);
  } catch (err) {
    console.warn(
      `[thermal] flir_extract.py failed for ${path.basename(imagePath)}, falling back to RGB method:`,
      (err as Error).message,
    );
    return await extractViaRgbFallback(imagePath);
  }
}

/** Primary path: use flirimageextractor Python bridge */
async function extractViaFlirTool(
  imagePath: string,
): Promise<{ stats: ThermalStats; thermalData: Float32Array }> {
  const { stdout, stderr } = await execFileAsync(
    "python3",
    [FLIR_EXTRACT_SCRIPT, imagePath],
    { maxBuffer: 64 * 1024 * 1024 }, // 64 MB — large images produce big base64 blobs
  );

  // flirimageextractor prints "File paths successfully generated: ..." to
  // stdout before our JSON.  Find the first '{' and parse from there.
  // If stderr contains a JSON error object from our script, throw that.
  if (stderr && stderr.trim()) {
    let msg = stderr.trim();
    try { msg = JSON.parse(msg).error ?? msg; } catch {}
    throw new Error(msg);
  }

  const jsonStart = stdout.indexOf('{');
  if (jsonStart === -1) {
    throw new Error(`No JSON found in flir_extract.py output: ${stdout.slice(0, 200)}`);
  }

  const result = JSON.parse(stdout.slice(jsonStart));
  if (result.error) throw new Error(result.error);

  const { width, height, min, max, mean, median, std, data: b64 } = result;

  // Decode base64 float32 buffer (raw °C values — not normalised)
  const raw = Buffer.from(b64, "base64");
  const thermalData = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);

  return {
    stats: { min, max, mean, median, std, width, height },
    thermalData,
  };
}

/**
 * Fallback: derive relative thermal values from the rendered RGB image.
 * Used only when flirimageextractor is unavailable or the file is not a
 * true FLIR radiometric JPEG.
 */
async function extractViaRgbFallback(
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

  for (let i = 0; i < pixelCount; i++) {
    const offset = i * 3;
    // Weighted luminance emphasising red channel (iron palette)
    thermalData[i] = (data[offset] * 0.5 + data[offset + 1] * 0.35 + data[offset + 2] * 0.15) / 255;
  }

  let sum = 0, min = Infinity, max = -Infinity;
  for (let i = 0; i < pixelCount; i++) {
    const v = thermalData[i];
    sum += v;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const mean = sum / pixelCount;

  let sqDiffSum = 0;
  for (let i = 0; i < pixelCount; i++) {
    const diff = thermalData[i] - mean;
    sqDiffSum += diff * diff;
  }
  const std = Math.sqrt(sqDiffSum / pixelCount);

  const sampleSize = Math.min(10000, pixelCount);
  const sample: number[] = [];
  const step = Math.floor(pixelCount / sampleSize);
  for (let i = 0; i < pixelCount; i += step) sample.push(thermalData[i]);
  sample.sort((a, b) => a - b);
  const median = sample[Math.floor(sample.length / 2)];

  return {
    stats: { min, max, mean, median, std, width, height },
    thermalData,
  };
}

// ── Hotspot detection ──────────────────────────────────────────────────

/**
 * Detect hotspots using a statistical threshold on thermal data.
 *
 * Works on raw °C values from flirimageextractor. The sensitivity
 * multiplier controls how many standard deviations above the mean
 * triggers a detection:
 *   lower  = more sensitive (more spots detected)
 *   higher = less sensitive (only the very warmest regions)
 *
 * Typical values: 1.0 (very sensitive) to 3.0 (conservative).
 * Default: 2.0 (medium).
 *
 * Because the input is raw radiometric data (not a rendered image), there
 * is no need to mask a HUD region — the thermal array contains no overlaid
 * graphics.
 */
export function detectHotspots(
  thermalData: Float32Array,
  width: number,
  height: number,
  sensitivity: number = 2.0,
  minAreaPx: number = 20,
): DetectedSpot[] {
  const pixelCount = width * height;

  let sum = 0;
  for (let i = 0; i < pixelCount; i++) sum += thermalData[i];
  const mean = sum / pixelCount;

  let sqDiffSum = 0;
  for (let i = 0; i < pixelCount; i++) {
    const diff = thermalData[i] - mean;
    sqDiffSum += diff * diff;
  }
  const std = Math.sqrt(sqDiffSum / pixelCount);
  const threshold = mean + sensitivity * std;

  // Binary mask
  const mask = new Uint8Array(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    mask[i] = thermalData[i] > threshold ? 1 : 0;
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
      const region = flood(i, nextLabel++);
      if (region.length >= minAreaPx) regions.push(region);
    }
  }

  // Extract properties from each region
  const spots: DetectedSpot[] = [];
  for (const region of regions) {
    let maxVal = -Infinity;
    let maxIdx = 0;
    for (const idx of region) {
      if (thermalData[idx] > maxVal) {
        maxVal = thermalData[idx];
        maxIdx = idx;
      }
    }

    const y = Math.floor(maxIdx / width);
    const x = maxIdx % width;

    const delta = maxVal - mean;
    let severity: DetectedSpot["severity"];
    if (delta > 3 * std)         severity = "critical";
    else if (delta > 2 * std)    severity = "high";
    else if (delta > 1.5 * std)  severity = "medium";
    else                         severity = "low";

    spots.push({
      x,
      y,
      temperature: Math.round(maxVal * 100) / 100,
      areaSize: region.length,
      severity,
    });
  }

  spots.sort((a, b) => b.temperature - a.temperature);
  return spots;
}

// ── Labeled image generation ───────────────────────────────────────────

const SEVERITY_COLORS: Record<string, { r: number; g: number; b: number }> = {
  low:      { r: 255, g: 255, b: 0   },
  medium:   { r: 255, g: 165, b: 0   },
  high:     { r: 255, g: 69,  b: 0   },
  critical: { r: 255, g: 0,   b: 0   },
};

/**
 * Draw spot markers onto the original FLIR visual JPEG.
 * Spot coordinates are in thermal-array space and are scaled up to the
 * visual image dimensions before drawing.
 */
export async function createLabeledImage(
  inputPath: string,
  spotsData: Array<{
    x: number;
    y: number;
    spotNumber: number;
    severity: string;
    thermalWidth?: number;
    thermalHeight?: number;
  }>,
  outputPath: string,
): Promise<void> {
  const { data: imgData, info } = await sharp(inputPath)
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = info.width;
  const height = info.height;
  const channels = 3;
  const pixels = Buffer.from(imgData);

  for (const spot of spotsData) {
    const color = SEVERITY_COLORS[spot.severity] || SEVERITY_COLORS.medium;

    // Scale thermal coordinates to visual image dimensions
    const scaleX = spot.thermalWidth  ? width  / spot.thermalWidth  : 1;
    const scaleY = spot.thermalHeight ? height / spot.thermalHeight : 1;
    const cx = Math.min(Math.max(Math.round(spot.x * scaleX), 12), width - 12);
    const cy = Math.min(Math.max(Math.round(spot.y * scaleY), 12), height - 12);

    for (let dx = -8; dx <= 8; dx++) {
      setPixel(pixels, width, channels, cx + dx, cy, color);
      setPixel(pixels, width, channels, cx, cy + dx, color);
    }

    const r = 10;
    for (let angle = 0; angle < 360; angle += 2) {
      const rad = (angle * Math.PI) / 180;
      setPixel(pixels, width, channels, Math.round(cx + r * Math.cos(rad)), Math.round(cy + r * Math.sin(rad)), color);
    }

    const labelX = cx + 12;
    const labelY = cy - 8;
    for (let dy = 0; dy < 14; dy++)
      for (let dx = 0; dx < 16; dx++)
        setPixel(pixels, width, channels, labelX + dx, labelY + dy, { r: 0, g: 0, b: 0 });

    drawDigit(pixels, width, channels, labelX + 3, labelY + 2, spot.spotNumber, color);
  }

  await sharp(pixels, { raw: { width, height, channels } })
    .jpeg({ quality: 90 })
    .toFile(outputPath);
}

function setPixel(
  buf: Buffer, width: number, ch: number,
  x: number, y: number,
  color: { r: number; g: number; b: number },
) {
  if (x < 0 || y < 0 || x >= width) return;
  const idx = (y * width + x) * ch;
  if (idx < 0 || idx + 2 >= buf.length) return;
  buf[idx] = color.r;
  buf[idx + 1] = color.g;
  buf[idx + 2] = color.b;
}

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
  buf: Buffer, width: number, ch: number,
  x: number, y: number, num: number,
  color: { r: number; g: number; b: number },
) {
  const digits = String(num).split("").map(Number);
  let offsetX = x;
  for (const d of digits) {
    const pattern = DIGIT_PATTERNS[d] || DIGIT_PATTERNS[0];
    for (let row = 0; row < 5; row++) {
      for (let col = 0; col < 3; col++) {
        if (pattern[row][col]) {
          setPixel(buf, width, ch, offsetX + col * 2,     y + row * 2,     color);
          setPixel(buf, width, ch, offsetX + col * 2 + 1, y + row * 2,     color);
          setPixel(buf, width, ch, offsetX + col * 2,     y + row * 2 + 1, color);
          setPixel(buf, width, ch, offsetX + col * 2 + 1, y + row * 2 + 1, color);
        }
      }
    }
    offsetX += 8;
  }
}

// ── Save / load thermal data ───────────────────────────────────────────

export function saveThermalData(outputPath: string, data: Float32Array, width: number, height: number): void {
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
