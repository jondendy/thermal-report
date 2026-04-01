import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import {
  ArrowLeft,
  Save,
  FolderOpen,
  Settings as SettingsIcon,
  HardDrive,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";

interface AppSettings {
  driveSourceFolderId: string;
  driveSourceFolderName: string;
  driveOutputFolderId: string;
  driveOutputFolderName: string;
  autoSaveToDrive: boolean;
  defaultSensitivity: number;
  defaultInspectorName: string;
  organisationName: string;
  reportHeaderText: string;
  reportFooterText: string;
}

interface DriveFolder {
  id: string;
  name: string;
  mimeType: string;
}

interface DriveStatus {
  connected: boolean;
  email?: string;
}

export default function SettingsPage() {
  const [, navigate] = useLocation();
  const { toast } = useToast();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [browsing, setBrowsing] = useState<"source" | "output" | null>(null);
  const [driveFolders, setDriveFolders] = useState<DriveFolder[]>([]);
  const [currentParent, setCurrentParent] = useState<string>("root");
  const [breadcrumbs, setBreadcrumbs] = useState<{ id: string; name: string }[]>([{ id: "root", name: "My Drive" }]);
  const [loadingFolders, setLoadingFolders] = useState(false);

  // Load settings
  const { data: loadedSettings, isLoading } = useQuery({
    queryKey: ["/api/settings"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/settings");
      return res.json() as Promise<AppSettings>;
    },
  });

  // Load Drive connection status
  const { data: driveStatus } = useQuery({
    queryKey: ["/api/drive/status"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/drive/status");
      return res.json() as Promise<DriveStatus>;
    },
  });

  useEffect(() => {
    if (loadedSettings && !settings) {
      setSettings(loadedSettings);
    }
  }, [loadedSettings, settings]);

  // Save settings
  const saveMutation = useMutation({
    mutationFn: async (data: Partial<AppSettings>) => {
      const res = await apiRequest("PATCH", "/api/settings", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/settings"] });
      toast({ title: "Settings saved", description: "Your preferences have been updated." });
    },
    onError: (err: any) => {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    },
  });

  // Browse Drive folders
  const loadDriveFolders = async (parentId: string) => {
    setLoadingFolders(true);
    try {
      const res = await apiRequest("GET", `/api/drive/folders?parent=${parentId}`);
      const data = await res.json();
      setDriveFolders(data.folders || []);
      setCurrentParent(parentId);
    } catch (e: any) {
      toast({ title: "Drive Error", description: e.message, variant: "destructive" });
      setDriveFolders([]);
    } finally {
      setLoadingFolders(false);
    }
  };

  const startBrowsing = async (target: "source" | "output") => {
    setBrowsing(target);
    setBreadcrumbs([{ id: "root", name: "My Drive" }]);
    await loadDriveFolders("root");
  };

  const navigateFolder = async (folderId: string, folderName: string) => {
    setBreadcrumbs((prev) => [...prev, { id: folderId, name: folderName }]);
    await loadDriveFolders(folderId);
  };

  const navigateBreadcrumb = async (index: number) => {
    const crumb = breadcrumbs[index];
    setBreadcrumbs((prev) => prev.slice(0, index + 1));
    await loadDriveFolders(crumb.id);
  };

  const selectFolder = (folderId: string, folderName: string) => {
    if (!settings || !browsing) return;
    if (browsing === "source") {
      setSettings({ ...settings, driveSourceFolderId: folderId, driveSourceFolderName: folderName });
    } else {
      setSettings({ ...settings, driveOutputFolderId: folderId, driveOutputFolderName: folderName });
    }
    setBrowsing(null);
    setDriveFolders([]);
  };

  const sensitivityLabel = (val: number) => {
    if (val <= 1.2) return "Very High";
    if (val <= 1.7) return "High";
    if (val <= 2.3) return "Medium";
    if (val <= 2.8) return "Low";
    return "Very Low";
  };

  if (isLoading || !settings) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")} data-testid="button-back">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold flex items-center gap-2" data-testid="text-settings-title">
              <SettingsIcon className="w-5 h-5" />
              Settings
            </h1>
            <p className="text-xs text-muted-foreground">
              Configure Google Drive, defaults, and report preferences.
            </p>
          </div>
        </div>
        <Button
          onClick={() => saveMutation.mutate(settings)}
          disabled={saveMutation.isPending}
          data-testid="button-save-settings"
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-1" />
          )}
          Save Settings
        </Button>
      </div>

      <div className="space-y-6">
        {/* Google Drive Integration */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <HardDrive className="w-4 h-4" />
              Google Drive Integration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Connection status */}
            <div className="flex items-center gap-2">
              {driveStatus?.connected ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                  <span className="text-sm">Connected{driveStatus.email ? ` as ${driveStatus.email}` : ""}</span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Not connected — connect via your account settings to enable Drive features.</span>
                </>
              )}
            </div>

            {/* Source folder */}
            <div>
              <Label className="text-xs">Source Folder (FLIR images)</Label>
              <div className="flex items-center gap-2 mt-1">
                <Input
                  value={settings.driveSourceFolderName || "Not set"}
                  readOnly
                  className="h-8 text-xs bg-muted/50"
                  data-testid="input-source-folder"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs flex-shrink-0"
                  onClick={() => startBrowsing("source")}
                  disabled={!driveStatus?.connected}
                  data-testid="button-browse-source"
                >
                  <FolderOpen className="w-3 h-3 mr-1" />
                  Browse
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Where to pull FLIR thermal images from when creating surveys.
              </p>
            </div>

            {/* Output folder */}
            <div>
              <Label className="text-xs">Output Folder (completed reports)</Label>
              <div className="flex items-center gap-2 mt-1">
                <Input
                  value={settings.driveOutputFolderName || "Not set"}
                  readOnly
                  className="h-8 text-xs bg-muted/50"
                  data-testid="input-output-folder"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs flex-shrink-0"
                  onClick={() => startBrowsing("output")}
                  disabled={!driveStatus?.connected}
                  data-testid="button-browse-output"
                >
                  <FolderOpen className="w-3 h-3 mr-1" />
                  Browse
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Where to save completed PDF survey reports.
              </p>
            </div>

            {/* Auto-save toggle */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-xs">Auto-save reports to Drive</Label>
                <p className="text-[10px] text-muted-foreground">
                  Automatically upload PDFs to the output folder when generated.
                </p>
              </div>
              <Switch
                checked={settings.autoSaveToDrive}
                onCheckedChange={(v) => setSettings({ ...settings, autoSaveToDrive: v })}
                disabled={!settings.driveOutputFolderId}
                data-testid="switch-auto-save"
              />
            </div>

            {/* Folder browser dialog */}
            {browsing && (
              <div className="border rounded-md p-3 bg-muted/30">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium">
                    Select {browsing === "source" ? "source" : "output"} folder
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={() => setBrowsing(null)}
                  >
                    Cancel
                  </Button>
                </div>

                {/* Breadcrumbs */}
                <div className="flex items-center gap-1 mb-2 flex-wrap">
                  {breadcrumbs.map((crumb, i) => (
                    <span key={crumb.id} className="flex items-center gap-1">
                      {i > 0 && <span className="text-xs text-muted-foreground">/</span>}
                      <button
                        className="text-xs text-primary hover:underline"
                        onClick={() => navigateBreadcrumb(i)}
                      >
                        {crumb.name}
                      </button>
                    </span>
                  ))}
                </div>

                {/* Select current folder button */}
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-7 text-xs mb-2 w-full"
                  onClick={() => {
                    const current = breadcrumbs[breadcrumbs.length - 1];
                    selectFolder(current.id, breadcrumbs.map(c => c.name).join(" / "));
                  }}
                >
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  Select this folder
                </Button>

                {/* Folder list */}
                {loadingFolders ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                  </div>
                ) : driveFolders.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-3">
                    No subfolders in this directory.
                  </p>
                ) : (
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {driveFolders.map((folder) => (
                      <button
                        key={folder.id}
                        className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs hover:bg-muted transition-colors text-left"
                        onClick={() => navigateFolder(folder.id, folder.name)}
                      >
                        <FolderOpen className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                        <span className="truncate">{folder.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Survey Defaults */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              Survey Defaults
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs">Organisation Name</Label>
                <Input
                  className="h-8 text-xs mt-1"
                  value={settings.organisationName}
                  onChange={(e) => setSettings({ ...settings, organisationName: e.target.value })}
                  placeholder="e.g. Chesham Energy Group"
                  data-testid="input-org-name"
                />
              </div>
              <div>
                <Label className="text-xs">Default Surveyor Name</Label>
                <Input
                  className="h-8 text-xs mt-1"
                  value={settings.defaultInspectorName}
                  onChange={(e) => setSettings({ ...settings, defaultInspectorName: e.target.value })}
                  placeholder="e.g. Jon Dendy"
                  data-testid="input-default-inspector"
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs">
                  Default Sensitivity: {sensitivityLabel(settings.defaultSensitivity)}
                </Label>
                <span className="text-xs text-muted-foreground">{settings.defaultSensitivity.toFixed(1)}σ</span>
              </div>
              <Slider
                min={0.5}
                max={4.0}
                step={0.1}
                value={[settings.defaultSensitivity]}
                onValueChange={([v]) => setSettings({ ...settings, defaultSensitivity: v })}
                data-testid="slider-default-sensitivity"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                New surveys will use this sensitivity by default.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Report Customisation */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Report Customisation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-xs">Report Header</Label>
              <Input
                className="h-8 text-xs mt-1"
                value={settings.reportHeaderText}
                onChange={(e) => setSettings({ ...settings, reportHeaderText: e.target.value })}
                placeholder="Thermal Survey Report"
                data-testid="input-report-header"
              />
            </div>
            <div>
              <Label className="text-xs">Report Footer</Label>
              <Input
                className="h-8 text-xs mt-1"
                value={settings.reportFooterText}
                onChange={(e) => setSettings({ ...settings, reportFooterText: e.target.value })}
                placeholder="Generated by Thermal Survey Reporter"
                data-testid="input-report-footer"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
