import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { queryClient } from "@/lib/queryClient";
import { getSurveys, createSurvey, deleteSurvey, uploadImages } from "@/lib/api";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  Trash2,
  Thermometer,
  ArrowRight,
  Plus,
  Loader2,
  Settings,
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
    if (appSettings?.defaultInspectorName && !inspector) {
      setInspector(appSettings.defaultInspectorName);
    }
  }, [appSettings]);

  const { data: surveys = [], isLoading } = useQuery({
    queryKey: ["/api/surveys"],
    queryFn: getSurveys,
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
          <CardContent className="space-y-4">
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
              <Button variant="outline" onClick={() => setShowNew(false)}>
                Cancel
              </Button>
            </div>
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
