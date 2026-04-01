/**
 * PDF Report Generator — purely logic-driven, no AI.
 *
 * Produces a professional thermal survey report PDF from:
 * - Survey metadata (address, inspector, date)
 * - Thermal images with labeled hotspots
 * - Spot data with types and temperatures
 * - Assessor notes and filtered recommendations
 * - Energy recommendations database (keyed by spot type)
 */

import PDFDocument from "pdfkit";
import fs from "fs";
import path from "path";
import type { Survey, Image, Spot, AssessorNote } from "@shared/schema";

// Load energy recommendations
let recommendations: Record<string, any> = {};
try {
  const recPath = path.join(process.cwd(), "server", "data", "energy_recommendations.json");
  if (fs.existsSync(recPath)) {
    recommendations = JSON.parse(fs.readFileSync(recPath, "utf-8"));
  }
} catch (e) {
  console.warn("Could not load energy_recommendations.json, using defaults");
}

const SEVERITY_COLORS: Record<string, [number, number, number]> = {
  low: [180, 180, 30],
  medium: [220, 140, 20],
  high: [220, 60, 10],
  critical: [200, 0, 0],
};

const SEVERITY_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Moderate",
  high: "Significant",
  critical: "Critical",
};

interface ReportData {
  survey: Survey;
  images: Image[];
  spots: Spot[];
  notes: AssessorNote[];
}

export async function generatePdfReport(data: ReportData, outputPath: string): Promise<void> {
  const { survey, images: surveyImages, spots, notes } = data;

  const doc = new PDFDocument({
    size: "A4",
    margins: { top: 50, bottom: 50, left: 50, right: 50 },
    info: {
      Title: `Thermal Survey Report — ${survey.propertyAddress || "Property"}`,
      Author: "Thermal Survey Reporter",
      Subject: "Building Heat Loss Assessment",
    },
  });

  const stream = fs.createWriteStream(outputPath);
  doc.pipe(stream);

  const pageWidth = doc.page.width - 100; // margins
  const now = new Date();

  // ── Cover Page ─────────────────────────────────────────────────────

  doc.moveDown(6);
  doc.fontSize(28).font("Helvetica-Bold").text("Thermal Survey Report", { align: "center" });
  doc.moveDown(1);
  doc.fontSize(14).font("Helvetica").fillColor("#444444")
    .text("Building Heat Loss Assessment", { align: "center" });
  doc.moveDown(3);

  doc.fontSize(12).fillColor("#222222");
  const coverItems = [
    ["Property:", survey.propertyAddress || "Not specified"],
    ["Surveyor:", survey.inspectorName || "Not specified"],
    ["Survey Date:", now.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })],
    ["Report Generated:", now.toLocaleString("en-GB")],
    ["Total Images:", String(surveyImages.length)],
    ["Hotspots Identified:", String(spots.length)],
  ];

  for (const [label, value] of coverItems) {
    doc.font("Helvetica-Bold").text(label, 120, undefined, { continued: true, width: 140 });
    doc.font("Helvetica").text(`  ${value}`);
    doc.moveDown(0.3);
  }

  // ── Executive Summary ──────────────────────────────────────────────

  doc.addPage();
  sectionHeading(doc, "Executive Summary");

  const severityCounts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const s of spots) {
    severityCounts[s.severity] = (severityCounts[s.severity] || 0) + 1;
  }

  doc.fontSize(11).font("Helvetica");
  doc.text(`This thermal survey identified ${spots.length} areas of potential heat loss across ${surveyImages.length} thermal image(s).`);
  doc.moveDown(0.5);

  if (severityCounts.critical > 0 || severityCounts.high > 0) {
    doc.text("Areas requiring attention:");
    doc.moveDown(0.3);
    if (severityCounts.critical > 0) {
      doc.fillColor(...SEVERITY_COLORS.critical)
        .text(`  •  ${severityCounts.critical} critical issue(s) requiring immediate attention`);
    }
    if (severityCounts.high > 0) {
      doc.fillColor(...SEVERITY_COLORS.high)
        .text(`  •  ${severityCounts.high} significant issue(s) to address promptly`);
    }
    if (severityCounts.medium > 0) {
      doc.fillColor(...SEVERITY_COLORS.medium)
        .text(`  •  ${severityCounts.medium} moderate issue(s) for consideration`);
    }
    if (severityCounts.low > 0) {
      doc.fillColor(...SEVERITY_COLORS.low)
        .text(`  •  ${severityCounts.low} minor issue(s) noted`);
    }
    doc.fillColor("#222222");
  } else {
    doc.text("No critical or high-severity issues were identified. Moderate and minor areas of heat loss are detailed below.");
  }

  // ── Findings by Image ─────────────────────────────────────────────

  doc.addPage();
  sectionHeading(doc, "Detailed Findings");

  for (const img of surveyImages) {
    const imgSpots = spots.filter((s) => s.imageId === img.id);
    if (imgSpots.length === 0) continue;

    doc.moveDown(0.5);
    doc.fontSize(13).font("Helvetica-Bold").text(`Image: ${img.filename}`);
    doc.fontSize(10).font("Helvetica").fillColor("#666666");

    if (img.minTemp !== null && img.maxTemp !== null) {
      doc.text(`Temperature range: ${formatTemp(img.minTemp)} to ${formatTemp(img.maxTemp)}`);
    }
    doc.fillColor("#222222");

    // Include labeled image if it exists
    const labeledPath = img.labeledPath;
    if (labeledPath && fs.existsSync(labeledPath)) {
      doc.moveDown(0.3);
      try {
        const imgWidth = Math.min(pageWidth, 400);
        doc.image(labeledPath, { width: imgWidth });
      } catch (e) {
        doc.text("[Image could not be embedded]");
      }
    }

    doc.moveDown(0.5);

    // Table of spots for this image
    for (const spot of imgSpots) {
      const color = SEVERITY_COLORS[spot.severity] || SEVERITY_COLORS.medium;
      const sevLabel = SEVERITY_LABELS[spot.severity] || spot.severity;

      // Check if we need a new page
      if (doc.y > doc.page.height - 120) {
        doc.addPage();
      }

      doc.fontSize(11).font("Helvetica-Bold").fillColor(...color);
      doc.text(`Spot #${spot.spotNumber} — ${spot.spotType} (${sevLabel})`);
      doc.fillColor("#222222").font("Helvetica").fontSize(10);

      const relTemp = spot.temperature !== null ? `Relative thermal value: ${spot.temperature}` : "";
      doc.text(`  Location: (${spot.pixelX}, ${spot.pixelY})  ${relTemp}`);

      // Type-specific description from recommendations database
      const rec = recommendations[spot.spotType];
      if (rec && rec.description) {
        doc.text(`  ${rec.description}`, { width: pageWidth - 20 });
      }

      // Assessor note if present
      const note = notes.find((n) => n.spotNumber === spot.spotNumber);
      if (note && note.note) {
        doc.moveDown(0.2);
        doc.font("Helvetica-Oblique").text(`  Assessor note: ${note.note}`, { width: pageWidth - 20 });
        doc.font("Helvetica");
      }

      doc.moveDown(0.3);
    }

    doc.moveDown(0.5);
  }

  // ── Recommendations ────────────────────────────────────────────────

  doc.addPage();
  sectionHeading(doc, "Recommendations");

  // Group spots by type for combined recommendations
  const spotsByType: Record<string, Spot[]> = {};
  for (const spot of spots) {
    if (!spotsByType[spot.spotType]) spotsByType[spot.spotType] = [];
    spotsByType[spot.spotType].push(spot);
  }

  // Priority ordering
  const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const sortedTypes = Object.entries(spotsByType).sort((a, b) => {
    const recA = recommendations[a[0]];
    const recB = recommendations[b[0]];
    const pA = recA ? priorityOrder[recA.priority] ?? 1 : 1;
    const pB = recB ? priorityOrder[recB.priority] ?? 1 : 1;
    return pA - pB;
  });

  for (const [spotType, typeSpots] of sortedTypes) {
    if (doc.y > doc.page.height - 100) doc.addPage();

    const rec = recommendations[spotType];
    const spotNums = typeSpots.map((s) => `#${s.spotNumber}`).join(", ");

    doc.fontSize(12).font("Helvetica-Bold").text(`${spotType} (Spots: ${spotNums})`);

    if (rec) {
      if (rec.savings) {
        doc.fontSize(10).font("Helvetica").fillColor("#016970")
          .text(`Estimated savings: ${rec.savings}`);
        doc.fillColor("#222222");
      }

      // Filter out recommendations that the assessor has removed
      const removedIndices: number[] = [];
      for (const note of notes) {
        if (typeSpots.some((s) => s.spotNumber === note.spotNumber)) {
          try {
            const removed = JSON.parse(note.removedRecommendations || "[]");
            removedIndices.push(...removed);
          } catch {}
        }
      }

      const advice: string[] = rec.advice || [];
      const filteredAdvice = advice.filter((_: string, i: number) => !removedIndices.includes(i));

      if (filteredAdvice.length > 0) {
        doc.fontSize(10).font("Helvetica");
        for (const item of filteredAdvice) {
          doc.text(`  •  ${item}`, { width: pageWidth - 20 });
        }
      }

      // Show assessor notes for this type
      for (const spot of typeSpots) {
        const note = notes.find((n) => n.spotNumber === spot.spotNumber);
        if (note && note.note) {
          doc.moveDown(0.2);
          doc.font("Helvetica-Oblique").fontSize(10)
            .text(`  Note for spot #${spot.spotNumber}: ${note.note}`, { width: pageWidth - 20 });
          doc.font("Helvetica");
        }
      }
    } else {
      doc.fontSize(10).font("Helvetica").text("  No specific recommendations available for this type.");
    }

    doc.moveDown(0.8);
  }

  // ── Footer ─────────────────────────────────────────────────────────

  if (doc.y > doc.page.height - 80) doc.addPage();
  doc.moveDown(2);
  doc.fontSize(9).font("Helvetica").fillColor("#888888");
  doc.text("This report was generated by Thermal Survey Reporter — a tool for volunteer energy assessors.", { align: "center" });
  doc.text("All temperature values are relative measurements derived from thermal camera imagery.", { align: "center" });
  doc.text("Recommendations are based on UK building stock guidance and Energy Saving Trust standards.", { align: "center" });

  doc.end();

  return new Promise((resolve, reject) => {
    stream.on("finish", resolve);
    stream.on("error", reject);
  });
}

function sectionHeading(doc: PDFKit.PDFDocument, text: string) {
  doc.fontSize(18).font("Helvetica-Bold").fillColor("#01696F").text(text);
  doc.moveDown(0.3);
  doc.moveTo(50, doc.y).lineTo(545, doc.y).strokeColor("#01696F").lineWidth(1).stroke();
  doc.moveDown(0.5);
  doc.fillColor("#222222");
}

function formatTemp(val: number | null): string {
  if (val === null || val === undefined) return "N/A";
  return val.toFixed(1);
}
