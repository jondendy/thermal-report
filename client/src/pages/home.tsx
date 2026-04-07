import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { queryClient } from "@/lib/queryClient";
import { getSurveys, createSurvey, deleteSurvey, uploadImages, getDriveProperties, importDriveImages } from "@/lib/api";
import type { DriveProperty, DriveImage } from "@/lib/api";
import { getDriveFolderFiles } from "@/lib/api";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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
  ImageOff,
} from "lucide-react";

const STATUS_BADGES: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  uploading: { label: "Uploading", variant: "outline" },
  reviewing: { label: "Reviewing Spots", variant: "secondary" },
  editing_notes: { label: "Editing Notes", variant: "default" },
  complete: { label: "Complete", variant: "default" },
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function HomePage() {
  const [, navigate] = useLocation();
  const [showNew, setShowNew] = useState(false);
  const [address, setAddress] = useState("");
  const [inspector, setInspector] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Drive import state
  const [selectedProperty, setSelectedProperty] = useState<DriveProperty | null>(null);
  const [loadingFolderFiles, setLoadingFolderFiles] = useState(false);
  const [driveInspector, setDriveInspector] = useState("");
  const [importing, setImporting] = useState(false);

  // File selection — empty Set means nothing ticked (start deselected)
  const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(new Set());

  // Load default inspector name from settings
  const { data: appSettings } = useQuery({
    queryKey: ["/api/settings"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/settings");
      return res.json();
    },
  });

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
      const survey = await createSurvey({ propertyAddress: address, inspectorName: inspector });
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
      if (selectedFileIds.size === 0) throw new Error("No files selected");
      setImporting(true);
      const imagesToImport = selectedProperty.images.filter((img) =>
        selectedFileIds.has(img.fileId)
      );
      return importDriveImages({
        propertyName: selectedProperty.folderName,
        inspectorName: driveInspector,
        images: imagesToImport.map((img) => ({ name: img.name, url: img.downloadUrl })),
      });
    },
    onSuccess: (survey) => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys"] });
      setShowNew(false);
      setSelectedProperty(null);
      setSelectedFileIds(new Set());
      setImporting(false);
      navigate(`/review/${survey.id}`);
    },
    onError: () => setImporting(false),
  });

  function toggleFile(fileId: string) {
    setSelectedFileIds((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  }

  function selectAllFiles() {
    if (!selectedProperty) return;
    setSelectedFileIds(new Set(selectedProperty.images.map((img) => img.fileId)));
  }

  function deselectAllFiles() {
    setSelectedFileIds(new Set());
  }

  const allSelected =
    selectedProperty !== null &&
    selectedProperty.images.length > 0 &&
    selectedFileIds.size === selectedProperty.images.length;

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
              <TabsList className="mb-4">
                <TabsTrigger value="upload">
                  <Upload className="w-4 h-4 mr-1.5" />
                  Upload Files
                </TabsTrigger>
                <TabsTrigger value="drive">
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
                    />
                  </div>
                  <div>
                    <Label htmlFor="inspector">Surveyor Name</Label>
                    <Input
                      id="inspector"
                      placeholder="e.g. Jon Dendy"
                      value={inspector}
                      onChange={(e) => setInspector(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="files">Thermal Images (JPEG, max 8)</Label>
                  <Input id="files" type="file" accept=".jpg,.jpeg" multiple ref={fileRef} className="mt-1" />
                  <p className="text-xs text-muted-foreground mt-1">
                    Upload radiometric JPEG images from your FLIR thermal camera.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => createMutation.mutate()} disabled={uploading}>
                    {uploading ? (
                      <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Processing...</>
                    ) : (
                      <><Upload className="w-4 h-4 mr-1" />Upload & Process</>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
                </div>
              </TabsContent>

              {/* ── Tab 2: Import from Drive ── */}
              <TabsContent value="drive" className="space-y-4">
                {driveLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mr-2" />
                    <span className="text-sm text-muted-foreground">Loading property folders…</span>
                  </div>
                ) : driveProperties.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <HardDrive className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No property folders found.</p>
                    <Button variant="outline" size="sm" className="mt-3" onClick={() => refetchDrive()}>Refresh</Button>
                  </div>
                ) : (
                  <>
                    {/* Step 1: Property folder list */}
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {driveProperties.map((prop) => (
                        <button
                          key={prop.folderId}
                          type="button"
                          onClick={async () => {
                            if (selectedProperty?.folderId === prop.folderId) {
                              setSelectedProperty(null);
                              setSelectedFileIds(new Set());
                            } else {
                              setLoadingFolderFiles(true);
                              setSelectedFileIds(new Set()); // start deselected
                              try {
                                const images = await getDriveFolderFiles(prop.folderId);
                                setSelectedProperty({ ...prop, images, thermalCount: images.length });
                                // Do NOT auto-select — user chooses which files to import
                              } finally {
                                setLoadingFolderFiles(false);
                              }
                            }
                          }}
                          className={[
                            "w-full text-left rounded-lg border px-4 py-3 transition-colors",
                            selectedProperty?.folderId === prop.folderId
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/40 hover:bg-muted/30",
                          ].join(" ")}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 min-w-0">
                              <FolderOpen className="w-4 h-4 text-primary flex-shrink-0" />
                              <span className="font-medium text-sm truncate">{prop.folderName}</span>
                            </div>
                            {selectedProperty?.folderId === prop.folderId ? (
                              <Badge variant="default">
                                {selectedFileIds.size} of {selectedProperty.images.length} selected
                              </Badge>
                            ) : (
                              <Badge variant="secondary">{prop.thermalCount} thermal</Badge>
                            )}
                          </div>
                          {prop.lastModified && (
                            <p className="text-xs text-muted-foreground mt-1 ml-6">
                              Modified {new Date(prop.lastModified).toLocaleDateString("en-GB")}
                            </p>
                          )}
                        </button>
                      ))}
                    </div>

                    {/* Loading spinner while fetching file list */}
                    {loadingFolderFiles && (
                      <div className="flex items-center justify-center py-6">
                        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground mr-2" />
                        <span className="text-sm text-muted-foreground">Loading files…</span>
                      </div>
                    )}

                    {/* Step 2: File selection checklist with thumbnails */}
                    {selectedProperty && !loadingFolderFiles && selectedProperty.images.length > 0 && (
                      <div className="border rounded-lg overflow-hidden">
                        {/* Header: select-all + count */}
                        <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/30">
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id="select-all-files"
                              checked={allSelected}
                              onCheckedChange={(checked) => checked ? selectAllFiles() : deselectAllFiles()}
                            />
                            <label htmlFor="select-all-files" className="text-xs font-medium cursor-pointer select-none">
                              {allSelected ? "Deselect all" : "Select all"}
                            </label>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {selectedFileIds.size} of {selectedProperty.images.length} selected
                          </span>
                        </div>

                        {/* Scrollable file list */}
                        <ul className="max-h-64 overflow-y-auto divide-y">
                          {selectedProperty.images.map((img: DriveImage) => (
                            <li key={img.fileId}>
                              <label
                                htmlFor={`file-${img.fileId}`}
                                className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/20 transition-colors"
                              >
                                <Checkbox
                                  id={`file-${img.fileId}`}
                                  checked={selectedFileIds.has(img.fileId)}
                                  onCheckedChange={() => toggleFile(img.fileId)}
                                />
                                {/* Thumbnail */}
                                <div className="w-12 h-9 rounded overflow-hidden flex-shrink-0 bg-muted flex items-center justify-center">
                                  {img.thumbnailLink ? (
                                    <img
                                      src={img.thumbnailLink}
                                      alt={img.name}
                                      className="w-full h-full object-cover"
                                      loading="lazy"
                                    />
                                  ) : (
                                    <ImageOff className="w-4 h-4 text-muted-foreground" />
                                  )}
                                </div>
                                <span className="flex-1 text-sm font-mono truncate" title={img.name}>
                                  {img.name}
                                </span>
                                {img.size > 0 && (
                                  <span className="text-xs text-muted-foreground flex-shrink-0">
                                    {formatBytes(img.size)}
                                  </span>
                                )}
                              </label>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Step 3: Surveyor name + Import button */}
                    {selectedProperty && !loadingFolderFiles && (
                      <div className="border-t pt-4 space-y-3">
                        <div>
                          <Label htmlFor="drive-inspector">Surveyor Name</Label>
                          <Input
                            id="drive-inspector"
                            placeholder="e.g. Jon Dendy"
                            value={driveInspector}
                            onChange={(e) => setDriveInspector(e.target.value)}
                          />
                        </div>
                        {selectedFileIds.size === 0 && (
                          <p className="text-xs text-amber-600">Select at least one file to import.</p>
                        )}
                        <div className="flex gap-2">
                          <Button
                            onClick={() => importMutation.mutate()}
                            disabled={importing || selectedFileIds.size === 0}
                          >
                            {importing ? (
                              <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Importing…</>
                            ) : (
                              <><CloudDownload className="w-4 h-4 mr-1" />
                                Import & Process{selectedFileIds.size > 0 ? ` (${selectedFileIds.size})` : ""}
                              </>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => { setSelectedProperty(null); setSelectedFileIds(new Set()); }}
                          >
                            Deselect
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end">
                      <Button variant="ghost" size="sm" onClick={() => refetchDrive()}>Refresh folders</Button>
                    </div>
                  </>
                )}

                <div className="flex justify-start">
                  <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
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
              survey.status === "complete" || survey.status === "editing_notes"
                ? `/notes/${survey.id}`
                : `/review/${survey.id}`;
            return (
              <Card
                key={survey.id}
                className="hover:border-primary/30 transition-colors cursor-pointer"
                onClick={() => navigate(nextPage)}
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
                      onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(survey.id); }}
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
