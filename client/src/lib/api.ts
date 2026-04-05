import { apiRequest, API_BASE } from "./queryClient";

// Survey types
export interface Survey {
  id: number;
  propertyAddress: string;
  inspectorName: string;
  sensitivity: number;
  status: string;
  createdAt: string;
}

export interface ThermalImage {
  id: number;
  surveyId: number;
  filename: string;
  originalPath: string;
  labeledPath: string;
  thermalDataPath: string;
  minTemp: number | null;
  maxTemp: number | null;
  meanTemp: number | null;
  medianTemp: number | null;
  stdTemp: number | null;
  thermalWidth: number | null;
  thermalHeight: number | null;
  visualWidth: number | null;
  visualHeight: number | null;
}

export interface Spot {
  id: number;
  surveyId: number;
  imageId: number;
  spotNumber: number;
  spotType: string;
  temperature: number | null;
  severity: string;
  pixelX: number;
  pixelY: number;
  areaSize: number;
  isAutoDetected: number;
  isDeleted: number;
}

export interface AssessorNote {
  id: number;
  surveyId: number;
  spotNumber: number;
  note: string;
  removedRecommendations: string;
}

export interface Recommendations {
  [key: string]: {
    advice: string[];
    savings: string;
    priority: string;
    description: string;
  };
}

// API functions
export async function createSurvey(data: Partial<Survey>): Promise<Survey> {
  const res = await apiRequest("POST", "/api/surveys", data);
  return res.json();
}

export async function getSurveys(): Promise<Survey[]> {
  const res = await apiRequest("GET", "/api/surveys");
  return res.json();
}

export async function getSurvey(id: number): Promise<Survey> {
  const res = await apiRequest("GET", `/api/surveys/${id}`);
  return res.json();
}

export async function updateSurvey(id: number, data: Partial<Survey>): Promise<Survey> {
  const res = await apiRequest("PATCH", `/api/surveys/${id}`, data);
  return res.json();
}

export async function deleteSurvey(id: number): Promise<void> {
  await apiRequest("DELETE", `/api/surveys/${id}`);
}

export async function uploadImages(surveyId: number, files: FileList): Promise<any> {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("files", files[i]);
  }
  const res = await fetch(`${API_BASE}/api/surveys/${surveyId}/images`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getImages(surveyId: number): Promise<ThermalImage[]> {
  const res = await apiRequest("GET", `/api/surveys/${surveyId}/images`);
  return res.json();
}

export async function getSpots(surveyId: number): Promise<Spot[]> {
  const res = await apiRequest("GET", `/api/surveys/${surveyId}/spots`);
  return res.json();
}

export async function addSpot(surveyId: number, data: Partial<Spot>): Promise<Spot> {
  const res = await apiRequest("POST", `/api/surveys/${surveyId}/spots`, data);
  return res.json();
}

export async function updateSpot(spotId: number, data: Partial<Spot>): Promise<Spot> {
  const res = await apiRequest("PATCH", `/api/spots/${spotId}`, data);
  return res.json();
}

export async function deleteSpot(spotId: number): Promise<void> {
  await apiRequest("DELETE", `/api/spots/${spotId}`);
}

export async function reprocessSurvey(surveyId: number, sensitivity: number): Promise<any> {
  const res = await apiRequest("POST", `/api/surveys/${surveyId}/reprocess`, { sensitivity });
  return res.json();
}

export async function regenerateLabels(surveyId: number): Promise<void> {
  await apiRequest("POST", `/api/surveys/${surveyId}/regenerate-labels`);
}

export async function getNotes(surveyId: number): Promise<AssessorNote[]> {
  const res = await apiRequest("GET", `/api/surveys/${surveyId}/notes`);
  return res.json();
}

export async function saveNote(
  surveyId: number,
  spotNumber: number,
  note: string,
  removedRecommendations: number[]
): Promise<AssessorNote> {
  const res = await apiRequest("POST", `/api/surveys/${surveyId}/notes`, {
    spotNumber,
    note,
    removedRecommendations,
  });
  return res.json();
}

export async function generatePdf(surveyId: number): Promise<{ success: boolean; filename: string }> {
  const res = await apiRequest("POST", `/api/surveys/${surveyId}/generate-pdf`);
  return res.json();
}

export async function getRecommendations(): Promise<Recommendations> {
  const res = await apiRequest("GET", "/api/recommendations");
  return res.json();
}

// ── Drive Integration ──────────────────────────────────────────

export interface DriveProperty {
  folderName: string;
  folderId: string;
  images: { name: string; fileId: string; size: number; isThermal: boolean; downloadUrl: string }[];
  lastModified: string;
  thermalCount: number;
}

export async function getDriveProperties(): Promise<DriveProperty[]> {
  const settingsRes = await apiRequest("GET", "/api/settings");
  const settings = await settingsRes.json();
  const folderId = settings.driveSourceFolderId;
  if (!folderId) return [];
  const res = await apiRequest("GET", `/api/drive/folders?parent=${folderId}`);
  const data = await res.json();
  return (data.folders || []).map((f: { id: string; name: string }) => ({
    folderId: f.id,
    folderName: f.name,
    thermalCount: 0,
    lastModified: null,
    images: [],
  }));
}

export async function getDriveFolderFiles(folderId: string): Promise<DriveProperty["images"]> {
  const res = await apiRequest("GET", `/api/drive/folders?parent=${folderId}`);
  const data = await res.json();
  // Also fetch JPEGs directly in this folder
  const filesRes = await apiRequest("GET", `/api/drive/source-files-by-folder?folderId=${folderId}`);
  const filesData = await filesRes.json();
  return (filesData.files || []).map((f: any) => ({
    name: f.name,
    fileId: f.id,
    size: parseInt(f.size || "0"),
    isThermal: true,
    downloadUrl: f.downloadUrl || "",
  }));
}

export async function importDriveImages(data: {
  propertyName: string;
  inspectorName: string;
  images: { name: string; url: string }[];
}): Promise<Survey> {
  const res = await apiRequest("POST", "/api/drive/import-images", data);
  return res.json();
}

export async function exportPdfToDrive(filename: string): Promise<{ success: boolean; message: string }> {
  const res = await apiRequest("POST", "/api/drive/export-pdf", { filename });
  return res.json();
}
