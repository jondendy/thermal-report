import type { Express } from "express";
import type { Server } from "http";
import multer from "multer";
import path from "path";
import fs from "fs";
import sharp from "sharp";
import { storage } from "./storage";
import { processImage, detectHotspots, createLabeledImage, saveThermalData, loadThermalData } from "./thermal";
import { generatePdfReport } from "./pdf-report";
import { loadSettings, saveSettings } from "./settings";
import { listFolders, listJpegs, uploadFile, getDriveClient } from "./drive";
import type { Spot } from "@shared/schema";

// Configure multer for file uploads
const uploadDir = path.join(process.cwd(), "uploads");
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });

const upload = multer({
  dest: uploadDir,
  limits: { fileSize: 50 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if ([".jpg", ".jpeg"].includes(ext)) cb(null, true);
    else cb(new Error("Only JPEG files are allowed"));
  },
});

// Directory for generated reports
const reportsDir = path.join(process.cwd(), "reports");
if (!fs.existsSync(reportsDir)) fs.mkdirSync(reportsDir, { recursive: true });

/** Read the actual pixel dimensions of a JPEG via sharp */
async function getVisualDimensions(imagePath: string): Promise<{ width: number; height: number }> {
  const meta = await sharp(imagePath).metadata();
  return { width: meta.width ?? 640, height: meta.height ?? 480 };
}

export function registerRoutes(server: Server, app: Express) {
  // ── Survey CRUD ────────────────────────────────────────────────

  app.get("/api/surveys", (_req, res) => {
    const surveys = storage.getAllSurveys();
    res.json(surveys);
  });

  app.post("/api/surveys", (req, res) => {
    const survey = storage.createSurvey({
      propertyAddress: req.body.propertyAddress || "",
      inspectorName: req.body.inspectorName || "",
      sensitivity: req.body.sensitivity || 2.0,
      status: "uploading",
      createdAt: new Date().toISOString(),
    });
    res.json(survey);
  });

  app.get("/api/surveys/:id", (req, res) => {
    const survey = storage.getSurvey(Number(req.params.id));
    if (!survey) return res.status(404).json({ error: "Survey not found" });
    res.json(survey);
  });

  app.patch("/api/surveys/:id", (req, res) => {
    const survey = storage.updateSurvey(Number(req.params.id), req.body);
    if (!survey) return res.status(404).json({ error: "Survey not found" });
    res.json(survey);
  });

  app.delete("/api/surveys/:id", (req, res) => {
    storage.deleteSurvey(Number(req.params.id));
    res.json({ success: true });
  });

  // ── Image Upload & Processing ──────────────────────────────────

  app.post("/api/surveys/:id/images", upload.array("files", 8), async (req, res) => {
    const surveyId = Number(req.params.id);
    const survey = storage.getSurvey(surveyId);
    if (!survey) return res.status(404).json({ error: "Survey not found" });

    const files = req.files as Express.Multer.File[];
    if (!files || files.length === 0) {
      return res.status(400).json({ error: "No files uploaded" });
    }

    const results = [];
    for (const file of files) {
      const permDir = path.join(uploadDir, String(surveyId));
      if (!fs.existsSync(permDir)) fs.mkdirSync(permDir, { recursive: true });
      const permPath = path.join(permDir, file.originalname);
      fs.renameSync(file.path, permPath);

      try {
        const { stats, thermalData } = await processImage(permPath);
        const visual = await getVisualDimensions(permPath);

        const thermalDir = path.join(permDir, "thermal_data");
        if (!fs.existsSync(thermalDir)) fs.mkdirSync(thermalDir, { recursive: true });
        const thermalPath = path.join(thermalDir, `${path.parse(file.originalname).name}.bin`);
        saveThermalData(thermalPath, thermalData, stats.width, stats.height);

        const image = storage.createImage({
          surveyId,
          filename: file.originalname,
          originalPath: permPath,
          thermalDataPath: thermalPath,
          minTemp: stats.min,
          maxTemp: stats.max,
          meanTemp: stats.mean,
          medianTemp: stats.median,
          stdTemp: stats.std,
          thermalWidth: stats.width,
          thermalHeight: stats.height,
          visualWidth: visual.width,
          visualHeight: visual.height,
        });

        const detectedSpots = detectHotspots(thermalData, stats.width, stats.height, survey.sensitivity);

        let spotNumber = storage.getNextSpotNumber(surveyId);
        for (const ds of detectedSpots) {
          storage.createSpot({
            surveyId,
            imageId: image.id,
            spotNumber,
            spotType: "Unknown",
            temperature: ds.temperature,
            severity: ds.severity,
            pixelX: ds.x,
            pixelY: ds.y,
            areaSize: ds.areaSize,
            isAutoDetected: 1,
            isDeleted: 0,
          });
          spotNumber++;
        }

        results.push({
          imageId: image.id,
          filename: file.originalname,
          stats,
          spotsDetected: detectedSpots.length,
        });
      } catch (e: any) {
        results.push({ filename: file.originalname, error: e.message });
      }
    }

    await regenerateLabeledImages(surveyId);
    storage.updateSurvey(surveyId, { status: "reviewing" });
    res.json({ results });
  });

  // ── Get images for a survey ────────────────────────────────────

  app.get("/api/surveys/:id/images", (req, res) => {
    const images = storage.getImagesBySurvey(Number(req.params.id));
    res.json(images);
  });

  // ── Serve image files ──────────────────────────────────────────

  app.get("/api/images/:id/file", (req, res) => {
    const image = storage.getImage(Number(req.params.id));
    if (!image) return res.status(404).json({ error: "Image not found" });
    if (!fs.existsSync(image.originalPath)) return res.status(404).json({ error: "File not found" });
    res.sendFile(path.resolve(image.originalPath));
  });

  app.get("/api/images/:id/labeled", (req, res) => {
    const image = storage.getImage(Number(req.params.id));
    if (!image || !image.labeledPath) return res.status(404).json({ error: "Labeled image not found" });
    if (!fs.existsSync(image.labeledPath)) return res.status(404).json({ error: "File not found" });
    res.sendFile(path.resolve(image.labeledPath));
  });

  // ── Spots CRUD ─────────────────────────────────────────────────

  app.get("/api/surveys/:id/spots", (req, res) => {
    const spots = storage.getSpotsBySurvey(Number(req.params.id));
    res.json(spots);
  });

  app.post("/api/surveys/:id/spots", (req, res) => {
    const surveyId = Number(req.params.id);
    const spotNumber = storage.getNextSpotNumber(surveyId);
    const spot = storage.createSpot({
      surveyId,
      imageId: req.body.imageId,
      spotNumber,
      spotType: req.body.spotType || "Unknown",
      temperature: req.body.temperature || null,
      severity: req.body.severity || "medium",
      pixelX: req.body.pixelX,
      pixelY: req.body.pixelY,
      areaSize: req.body.areaSize || 0,
      isAutoDetected: 0,
      isDeleted: 0,
    });
    res.json(spot);
  });

  app.patch("/api/spots/:id", (req, res) => {
    const spot = storage.updateSpot(Number(req.params.id), req.body);
    if (!spot) return res.status(404).json({ error: "Spot not found" });
    res.json(spot);
  });

  app.delete("/api/spots/:id", (req, res) => {
    storage.updateSpot(Number(req.params.id), { isDeleted: 1 });
    res.json({ success: true });
  });

  // ── Re-process with new sensitivity ────────────────────────────

  app.post("/api/surveys/:id/reprocess", async (req, res) => {
    const surveyId = Number(req.params.id);
    const survey = storage.getSurvey(surveyId);
    if (!survey) return res.status(404).json({ error: "Survey not found" });

    const sensitivity = req.body.sensitivity ?? survey.sensitivity;
    storage.updateSurvey(surveyId, { sensitivity });

    // Delete existing auto-detected spots
    const existingSpots = storage.getSpotsBySurvey(surveyId);
    for (const spot of existingSpots) {
      if (spot.isAutoDetected) storage.updateSpot(spot.id, { isDeleted: 1 });
    }

    const images = storage.getImagesBySurvey(surveyId);
    let spotNumber = storage.getNextSpotNumber(surveyId);

    for (const img of images) {
      if (!img.originalPath || !fs.existsSync(img.originalPath)) continue;

      try {
        const { stats, thermalData } = await processImage(img.originalPath);
        const visual = await getVisualDimensions(img.originalPath);

        if (img.thermalDataPath) {
          saveThermalData(img.thermalDataPath, thermalData, stats.width, stats.height);
        }

        storage.updateImage(img.id, {
          minTemp: stats.min,
          maxTemp: stats.max,
          meanTemp: stats.mean,
          medianTemp: stats.median,
          stdTemp: stats.std,
          thermalWidth: stats.width,
          thermalHeight: stats.height,
          visualWidth: visual.width,
          visualHeight: visual.height,
        });

        const detected = detectHotspots(thermalData, stats.width, stats.height, sensitivity);
        for (const ds of detected) {
          storage.createSpot({
            surveyId,
            imageId: img.id,
            spotNumber,
            spotType: "Unknown",
            temperature: ds.temperature,
            severity: ds.severity,
            pixelX: ds.x,
            pixelY: ds.y,
            areaSize: ds.areaSize,
            isAutoDetected: 1,
            isDeleted: 0,
          });
          spotNumber++;
        }
      } catch (e: any) {
        console.error(`[reprocess] Failed to re-extract ${img.filename}:`, e.message);
        if (img.thermalDataPath) {
          const thermal = loadThermalData(img.thermalDataPath);
          if (thermal) {
            const detected = detectHotspots(thermal.data, thermal.width, thermal.height, sensitivity);
            for (const ds of detected) {
              storage.createSpot({
                surveyId,
                imageId: img.id,
                spotNumber,
                spotType: "Unknown",
                temperature: ds.temperature,
                severity: ds.severity,
                pixelX: ds.x,
                pixelY: ds.y,
                areaSize: ds.areaSize,
                isAutoDetected: 1,
                isDeleted: 0,
              });
              spotNumber++;
            }
          }
        }
      }
    }

    await regenerateLabeledImages(surveyId);
    const newSpots = storage.getSpotsBySurvey(surveyId);
    res.json({ spots: newSpots, sensitivity });
  });

  // ── Regenerate labeled images ──────────────────────────────────

  app.post("/api/surveys/:id/regenerate-labels", async (req, res) => {
    await regenerateLabeledImages(Number(req.params.id));
    res.json({ success: true });
  });

  // ── Assessor Notes ─────────────────────────────────────────────

  app.get("/api/surveys/:id/notes", (req, res) => {
    const notes = storage.getNotesBySurvey(Number(req.params.id));
    res.json(notes);
  });

  app.post("/api/surveys/:id/notes", (req, res) => {
    const note = storage.createOrUpdateNote({
      surveyId: Number(req.params.id),
      spotNumber: req.body.spotNumber,
      note: req.body.note || "",
      removedRecommendations: JSON.stringify(req.body.removedRecommendations || []),
    });
    res.json(note);
  });

  // ── PDF Report Generation ──────────────────────────────────────

  app.post("/api/surveys/:id/generate-pdf", async (req, res) => {
    const surveyId = Number(req.params.id);
    const survey = storage.getSurvey(surveyId);
    if (!survey) return res.status(404).json({ error: "Survey not found" });

    const images = storage.getImagesBySurvey(surveyId);
    const spots = storage.getSpotsBySurvey(surveyId);
    const notes = storage.getNotesBySurvey(surveyId);

    const sanitizedAddress = (survey.propertyAddress || `survey-${surveyId}`)
      .replace(/[^a-zA-Z0-9\s_-]/g, "")
      .trim()
      .replace(/\s+/g, "_");
    const pdfFilename = `Thermal_Survey_Report_${sanitizedAddress}.pdf`;
    const pdfPath = path.join(reportsDir, pdfFilename);

    try {
      await generatePdfReport({ survey, images, spots, notes }, pdfPath);
      storage.updateSurvey(surveyId, { status: "complete" });
      res.json({ success: true, filename: pdfFilename });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.get("/api/reports/:filename", (req, res) => {
    const filePath = path.join(reportsDir, req.params.filename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: "Report not found" });
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="${req.params.filename}"`);
    res.sendFile(path.resolve(filePath));
  });

  // ── Energy Recommendations (static data) ───────────────────────

  app.get("/api/recommendations", (_req, res) => {
    try {
      const recPath = path.join(process.cwd(), "server", "data", "energy_recommendations.json");
      if (fs.existsSync(recPath)) {
        const data = JSON.parse(fs.readFileSync(recPath, "utf-8"));
        res.json(data);
      } else {
        res.json({});
      }
    } catch {
      res.json({});
    }
  });

  // ── Settings ──────────────────────────────────────────────────

  app.get("/api/settings", (_req, res) => {
    const settings = loadSettings();
    res.json(settings);
  });

  app.patch("/api/settings", (req, res) => {
    const updated = saveSettings(req.body);
    res.json(updated);
  });

  // ── Google Drive Integration ──────────────────────────────────

  app.get("/api/drive/status", (_req, res) => {
    const settings = loadSettings();
    res.json({
      connected: !!(settings.driveSourceFolderId || settings.driveOutputFolderId),
      email: "",
    });
  });

  app.get("/api/drive/folders", async (req, res) => {
    const parentId = (req.query.parent as string) || "root";
    try {
      const folders = await listFolders(parentId);
      res.json({ folders, parentId });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.get("/api/drive/source-files", async (_req, res) => {
    const settings = loadSettings();
    if (!settings.driveSourceFolderId) {
      return res.json({ files: [], error: "No source folder configured" });
    }
    try {
      const files = await listJpegs(settings.driveSourceFolderId);
      res.json({ files, folderId: settings.driveSourceFolderId });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.get("/api/drive/folder-files", async (req, res) => {
    const folderId = req.query.folderId as string;
    if (!folderId) return res.status(400).json({ error: "folderId required" });
    try {
      const files = await listJpegs(folderId);
      res.json({ files });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.get("/api/drive/download-file", async (req, res) => {
    const fileId = req.query.fileId as string;
    if (!fileId) return res.status(400).json({ error: "fileId required" });
    try {
      const drive = getDriveClient();
      const meta = await drive.files.get({ fileId, fields: "name,mimeType" });
      const fileRes = await drive.files.get(
        { fileId, alt: "media" },
        { responseType: "stream" }
      );
      res.setHeader("Content-Type", meta.data.mimeType || "image/jpeg");
      res.setHeader("Content-Disposition", `attachment; filename="${meta.data.name}"`);
      (fileRes.data as any).pipe(res);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/drive/upload-report", async (req, res) => {
    const settings = loadSettings();
    if (!settings.driveOutputFolderId) {
      return res.status(400).json({ error: "No output folder configured" });
    }
    const { filename } = req.body;
    if (!filename) return res.status(400).json({ error: "No filename provided" });
    const filePath = path.join(reportsDir, filename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: "Report file not found" });
    try {
      const result = await uploadFile(settings.driveOutputFolderId, filePath, filename);
      res.json({ success: true, fileId: result.id, fileName: result.name });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // ── Drive Manifest Integration ─────────────────────────────────

  app.get("/api/drive/property-folders", (_req, res) => {
    const manifestPath = path.join(process.cwd(), "drive-manifest.json");
    try {
      const raw = fs.existsSync(manifestPath)
        ? JSON.parse(fs.readFileSync(manifestPath, "utf-8"))
        : { lastScanned: null, properties: [] };

      const properties = (raw.properties || []).map((prop: any) => {
        const thermalImages = (prop.images || []).filter(
          (img: any) => img.isThermal || img.size > 40 * 1024
        );
        return { ...prop, thermalCount: thermalImages.length };
      });

      res.json({
        lastScanned: raw.lastScanned,
        sourceFolder: raw.sourceFolder,
        outputFolder: raw.outputFolder,
        properties,
      });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/drive/import-images", async (req, res) => {
    const { propertyName, inspectorName, images } = req.body as {
      propertyName: string;
      inspectorName: string;
      images: { name: string; url: string }[];
    };

    if (!propertyName || !images || images.length === 0) {
      return res.status(400).json({ error: "propertyName and images are required" });
    }

    const survey = storage.createSurvey({
      propertyAddress: propertyName,
      inspectorName: inspectorName || "",
      sensitivity: 2.0,
      status: "uploading",
      createdAt: new Date().toISOString(),
    });

    const surveyId = survey.id;
    const permDir = path.join(uploadDir, String(surveyId));
    if (!fs.existsSync(permDir)) fs.mkdirSync(permDir, { recursive: true });

    const results = [];

    for (const img of images) {
      try {
        const drive = getDriveClient();
        const fileIdMatch = img.url.match(/fileId=([^&]+)/);
        const fileId = fileIdMatch ? fileIdMatch[1] : null;
        if (!fileId) throw new Error(`No fileId found in URL for ${img.name}`);

        const driveRes = await drive.files.get(
          { fileId, alt: "media" },
          { responseType: "arraybuffer" }
        );
        const buffer = Buffer.from(driveRes.data as ArrayBuffer);
        const permPath = path.join(permDir, img.name);
        fs.writeFileSync(permPath, buffer);

        const { stats, thermalData } = await processImage(permPath);
        const visual = await getVisualDimensions(permPath);

        const thermalDir = path.join(permDir, "thermal_data");
        if (!fs.existsSync(thermalDir)) fs.mkdirSync(thermalDir, { recursive: true });
        const thermalPath = path.join(thermalDir, `${path.parse(img.name).name}.bin`);
        saveThermalData(thermalPath, thermalData, stats.width, stats.height);

        const image = storage.createImage({
          surveyId,
          filename: img.name,
          originalPath: permPath,
          thermalDataPath: thermalPath,
          minTemp: stats.min,
          maxTemp: stats.max,
          meanTemp: stats.mean,
          medianTemp: stats.median,
          stdTemp: stats.std,
          thermalWidth: stats.width,
          thermalHeight: stats.height,
          visualWidth: visual.width,
          visualHeight: visual.height,
        });

        const detectedSpots = detectHotspots(thermalData, stats.width, stats.height, survey.sensitivity);

        let spotNumber = storage.getNextSpotNumber(surveyId);
        for (const ds of detectedSpots) {
          storage.createSpot({
            surveyId,
            imageId: image.id,
            spotNumber,
            spotType: "Unknown",
            temperature: ds.temperature,
            severity: ds.severity,
            pixelX: ds.x,
            pixelY: ds.y,
            areaSize: ds.areaSize,
            isAutoDetected: 1,
            isDeleted: 0,
          });
          spotNumber++;
        }

        results.push({
          imageId: image.id,
          filename: img.name,
          stats,
          spotsDetected: detectedSpots.length,
        });
      } catch (e: any) {
        results.push({ filename: img.name, error: e.message });
      }
    }

    await regenerateLabeledImages(surveyId);
    storage.updateSurvey(surveyId, { status: "reviewing" });
    const updatedSurvey = storage.getSurvey(surveyId);
    res.json({ ...updatedSurvey, results });
  });

  app.post("/api/drive/export-pdf", (req, res) => {
    const { filename } = req.body;
    if (!filename) return res.status(400).json({ error: "No filename provided" });
    const filePath = path.join(reportsDir, filename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: "Report file not found" });
    const exportQueuePath = path.join(process.cwd(), "drive-export-queue.json");
    const queue = fs.existsSync(exportQueuePath)
      ? JSON.parse(fs.readFileSync(exportQueuePath, "utf-8"))
      : [];
    queue.push({
      filename,
      filePath: path.resolve(filePath),
      queuedAt: new Date().toISOString(),
      exported: false,
    });
    fs.writeFileSync(exportQueuePath, JSON.stringify(queue, null, 2), "utf-8");
    res.json({ success: true, message: "Report queued for Google Drive export", filePath: path.resolve(filePath) });
  });

  app.get("/api/drive/export-status/:filename", (req, res) => {
    const exportQueuePath = path.join(process.cwd(), "drive-export-queue.json");
    if (!fs.existsSync(exportQueuePath)) return res.json({ queued: false, exported: false });
    const queue = JSON.parse(fs.readFileSync(exportQueuePath, "utf-8"));
    const entry = queue.find((e: any) => e.filename === req.params.filename);
    if (!entry) return res.json({ queued: false, exported: false });
    res.json({ queued: true, exported: entry.exported });
  });

  app.post("/api/drive/refresh-manifest", (req, res) => {
    const manifestPath = path.join(process.cwd(), "drive-manifest.json");
    try {
      const manifest = req.body;
      if (!manifest || typeof manifest !== "object") {
        return res.status(400).json({ error: "Invalid manifest body" });
      }
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf-8");
      res.json({ success: true });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });
}

// Helper: regenerate all labeled images for a survey.
// Passes thermalWidth/thermalHeight so createLabeledImage() can scale
// spot coordinates from thermal space (e.g. 160x120) up to the actual
// visual JPEG dimensions (e.g. 640x480) before drawing markers.
async function regenerateLabeledImages(surveyId: number): Promise<void> {
  const images = storage.getImagesBySurvey(surveyId);
  const allSpots = storage.getSpotsBySurvey(surveyId);

  for (const img of images) {
    const imgSpots = allSpots.filter((s) => s.imageId === img.id && !s.isDeleted);
    if (imgSpots.length === 0) continue;

    const labeledPath = img.originalPath.replace(/\.jpg$/i, "_labeled.jpg");
    try {
      await createLabeledImage(
        img.originalPath,
        imgSpots.map((s) => ({
          x: s.pixelX,
          y: s.pixelY,
          spotNumber: s.spotNumber,
          severity: s.severity,
          thermalWidth:  img.thermalWidth  ?? undefined,
          thermalHeight: img.thermalHeight ?? undefined,
        })),
        labeledPath,
      );
      storage.updateImage(img.id, { labeledPath });
    } catch (e) {
      console.error(`Failed to create labeled image for ${img.filename}:`, e);
    }
  }
}
