import { google } from "googleapis";
import path from "path";
import fs from "fs";

const KEY_FILE = path.join(process.cwd(), "service-account.json");

export function getDriveClient() {
  const auth = new google.auth.GoogleAuth({
    keyFile: KEY_FILE,
    scopes: ["https://www.googleapis.com/auth/drive"],
  });
  return google.drive({ version: "v3", auth });
}

export async function listFolders(parentId = "root") {
  const drive = getDriveClient();
  const res = await drive.files.list({
    q: `'${parentId}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false`,
    fields: "files(id,name)",
    pageSize: 100,
  });
  return res.data.files || [];
}

export async function listJpegs(folderId: string) {
  const drive = getDriveClient();
  const res = await drive.files.list({
    q: `'${folderId}' in parents and mimeType='image/jpeg' and trashed=false`,
    fields: "files(id,name,size,modifiedTime)",
    pageSize: 200,
  });
  return res.data.files || [];
}

export async function uploadFile(folderId: string, filePath: string, filename: string) {
  const drive = getDriveClient();
  const res = await drive.files.create({
    requestBody: { name: filename, parents: [folderId] },
    media: { mimeType: "application/pdf", body: fs.createReadStream(filePath) },
    fields: "id,name",
  });
  return res.data;
}
