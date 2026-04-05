import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { queryClient } from "@/lib/queryClient";
import { getSurveys, createSurvey, deleteSurvey, uploadImages, getDriveProperties, importDriveImages } from "@/lib/api";
import type { DriveProperty, getDriveFolderFiles } from "@/lib/api";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Upload,
  Trash2,
  Thermometer,
  ArrowRight,
  Plus,
  Loader2,
  Settings,
  FolderOpen,
  HardDrive,
  CloudDownload,
} from "lucide-react";

const STATUS_BADGES: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  uploading: { label: "Uploading", variant: "outline" },
  reviewing: { label: "Reviewing Spots", variant: "secondary" },
  editing_notes: { label: "Editing Notes", variant: "default" },
  complete: { label: "Complete", variant: "default" },
};

export default function HomePage() {
  const [, navigate] = useLocation();
  const [showNew, setShowNew] = useState(false);
  const [address, setAddress] = useState("");
  const [inspector, setInspector] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Drive import state
  const [selectedProperty, setSelectedProperty] = useState<DriveProperty | null>(null);
  const [driveInspector, setDriveInspector] = useState("");
  const [importing, setImporting] = useState(false);

  // Load default inspector name from settings
  const { data: appSettings } = useQuery({
    queryKey: ["/api/settings"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/settings");
      return res.json();
    },
  });

  // Pre-fill inspector when settings load
  useEffect(() => {
    if (appSettings?.defaultInspectorName) {
      if (!inspector) setInspector(appSettings.defaultInspectorName);
      if (!driveInspector) setDriveInspector(appSettings.defaultInspectorName);
    }
  }, [appSettings]);

  const { data: surveys = [], isLoading } = useQuery({
    queryKey: ["/api/surveys"],
    queryFn: getSurveys,
  });

  // Drive properties query — only runs when the panel is open
  const {
    data: driveProperties = [],
    isLoading: driveLoading,
    refetch: refetchDrive,
  } = useQuery({
    queryKey: ["/api/drive/property-folders"],
    queryFn: getDriveProperties,
    enabled: showNew,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const files = fileRef.current?.files;
      if (!files || files.length === 0) throw new Error("Select at least one image");

      setUploading(true);
      const survey = await createSurvey({
        propertyAddress: address,
        inspectorName: inspector,
      });
      await uploadImages(survey.id, files);
      return survey;
    },
    onSuccess: (survey) => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys"] });
      setShowNew(false);
      setAddress("");
      setInspector("");
      setUploading(false);
      navigate(`/review/${survey.id}`);
    },
    onError: () => setUploading(false),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSurvey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/surveys"] }),
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProperty) throw new Error("No property selected");
      setImporting(true);

      const thermalImages = selectedProperty.images.filter(
        (img) => img.isThermal || img.size > 40 * 1024
      );
      if (thermalImages.length === 0) throw new Error("No thermal images found in this folder");

      return importDriveImages({
        propertyName: selectedProperty.folderName,
        inspectorName: driveInspector,
        images: thermalImages.map((img) => ({ name: img.name, url: img.downloadUrl })),
      });
    },
    onSuccess: (survey) => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys"] });
      setShowNew(false);
      setSelectedProperty(null);
      setImporting(false);
      navigate(`/review/${survey.id}`);
    },
    onError: () => setImporting(false),
  });

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <Thermometer className="w-6 h-6 text-primary" />
            Thermal Survey Reporter
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload FLIR thermal images, review hotspots, and generate heat loss reports.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => navigate("/settings")} data-testid="button-settings">
            <Settings className="w-4 h-4" />
          </Button>
          <Button onClick={() => setShowNew(!showNew)} data-testid="button-new-survey">
            <Plus className="w-4 h-4 mr-1" />
            New Survey
          </Button>
        </div>
      </div>

      {showNew && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">New Thermal Survey</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="upload" data-testid="tabs-new-survey">
              <TabsList className="mb-4" data-testid="tablist-new-survey">
                <TabsTrigger value="upload" data-testid="tab-upload-files">
                  <Upload className="w-4 h-4 mr-1.5" />
                  Upload Files
                </TabsTrigger>
                <TabsTrigger value="drive" data-testid="tab-import-drive">
                  <HardDrive className="w-4 h-4 mr-1.5" />
                  Import from Drive
                </TabsTrigger>
              </TabsList>

              {/* ── Tab 1: Upload Files ── */}
              <TabsContent value="upload" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="address">Property Address</Label>
                    <Input
                      id="address"
                      placeholder="e.g. 14 High Street, Chesham"
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      data-testid="input-address"
                    />
                  </div>
                  <div>
                    <Label htmlFor="inspector">Surveyor Name</Label>
                    <Input
                      id="inspector"
                      placeholder="e.g. Jon Dendy"
                      value={inspector}
                      onChange={(e) => setInspector(e.target.value)}
                      data-testid="input-inspector"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="files">Thermal Images (JPEG, max 8)</Label>
                  <Input
                    id="files"
                    type="file"
                    accept=".jpg,.jpeg"
                    multiple
                    ref={fileRef}
                    className="mt-1"
                    data-testid="input-files"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Upload radiometric JPEG images from your FLIR thermal camera.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => createMutation.mutate()}
                    disabled={uploading}
                    data-testid="button-upload"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-1" />
                        Upload & Process
                      </>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => setShowNew(false)} data-testid="button-cancel-upload">
                    Cancel
                  </Button>
                </div>
              </TabsContent>

              {/* ── Tab 2: Import from Drive ── */}
              <TabsContent value="drive" className="space-y-4">
                {driveLoading ? (
                  <div className="flex items-center justify-center py-8" data-testid="drive-loading">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mr-2" />
                    <span className="text-sm text-muted-foreground">Loading property folders…</span>
                  </div>
                ) : driveProperties.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground" data-testid="drive-empty">
                    <HardDrive className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No property folders found. Ask your assistant to scan Google Drive.</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={() => refetchDrive()}
                      data-testid="button-drive-refresh"
                    >
                      Refresh
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="space-y-2 max-h-64 overflow-y-auto" data-testid="drive-property-list">
                      {driveProperties.map((prop) => (
                        <button
                          key={prop.folderId}
                          type="button"
                          onClick={async () => {
                              if (selectedProperty?.folderId === prop.folderId) {
                                  setSelectedProperty(null);
                              } else {
                                  const images = await getDriveFolderFiles(prop.folderId);
                                  setSelectedProperty({ ...prop, images, thermalCount: images.length });
                              }
                          }}
                          className={[
                            "w-full text-left rounded-lg border px-4 py-3 transition-colors",
                            selectedProperty?.folderId === prop.folderId
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/40 hover:bg-muted/30",
                          ].join(" ")}
                          data-testid={`card-drive-property-${prop.folderId}`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 min-w-0">
                              <FolderOpen className="w-4 h-4 text-primary flex-shrink-0" />
                              <span className="font-medium text-sm truncate" data-testid={`text-property-name-${prop.folderId}`}>
                                {prop.folderName}
                              </span>
                            </div>
                            <Badge variant="secondary" data-testid={`badge-thermal-count-${prop.folderId}`}>
                              {prop.thermalCount} thermal
                            </Badge>
                          </div>
                          {prop.lastModified && (
                            <p className="text-xs text-muted-foreground mt-1 ml-6" data-testid={`text-last-modified-${prop.folderId}`}>
                              Modified {new Date(prop.lastModified).toLocaleDateString("en-GB")}
                            </p>
                          )}
                        </button>
                      ))}
                    </div>

                    {selectedProperty && (
                      <div className="border-t pt-4 space-y-3" data-testid="drive-import-form">
                        <div>
                          <Label htmlFor="drive-inspector">Surveyor Name</Label>
                          <Input
                            id="drive-inspector"
                            placeholder="e.g. Jon Dendy"
                            value={driveInspector}
                            onChange={(e) => setDriveInspector(e.target.value)}
                            data-testid="input-drive-inspector"
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {selectedProperty.thermalCount} thermal image{selectedProperty.thermalCount !== 1 ? "s" : ""} will be
                          imported from <strong>{selectedProperty.folderName}</strong>.
                        </p>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => importMutation.mutate()}
                            disabled={importing}
                            data-testid="button-import-drive"
                          >
                            {importing ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                                Importing…
                              </>
                            ) : (
                              <>
                                <CloudDownload className="w-4 h-4 mr-1" />
                                Import & Process
                              </>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setSelectedProperty(null)}
                            data-testid="button-deselect-property"
                          >
                            Deselect
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => refetchDrive()}
                        data-testid="button-drive-refresh-bottom"
                      >
                        Refresh folders
                      </Button>
                    </div>
                  </>
                )}

                <div className="flex justify-start">
                  <Button variant="outline" onClick={() => setShowNew(false)} data-testid="button-cancel-drive">
                    Cancel
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : surveys.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Thermometer className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>No surveys yet. Create a new survey to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {surveys.map((survey) => {
            const badge = STATUS_BADGES[survey.status] || STATUS_BADGES.uploading;
            const nextPage =
              survey.status === "complete"
                ? `/notes/${survey.id}`
                : survey.status === "editing_notes"
                  ? `/notes/${survey.id}`
                  : `/review/${survey.id}`;

            return (
              <Card
                key={survey.id}
                className="hover:border-primary/30 transition-colors cursor-pointer"
                onClick={() => navigate(nextPage)}
                data-testid={`card-survey-${survey.id}`}
              >
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">
                        {survey.propertyAddress || "Unnamed Property"}
                      </span>
                      <Badge variant={badge.variant}>{badge.label}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {survey.inspectorName && `Surveyor: ${survey.inspectorName} · `}
                      {new Date(survey.createdAt).toLocaleDateString("en-GB")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this survey?")) deleteMutation.mutate(survey.id);
                      }}
                      data-testid={`button-delete-${survey.id}`}
                    >
                      <Trash2 className="w-4 h-4 text-muted-foreground" />
                    </Button>
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
