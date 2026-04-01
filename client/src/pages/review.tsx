import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useParams, useLocation } from "wouter";
import { queryClient, API_BASE } from "@/lib/queryClient";
import {
  getSurvey,
  getImages,
  getSpots,
  updateSpot,
  deleteSpot,
  addSpot,
  reprocessSurvey,
  updateSurvey,
} from "@/lib/api";
import type { Spot, ThermalImage } from "@/lib/api";
import { SPOT_TYPES } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowLeft,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Trash2,
  Plus,
  SlidersHorizontal,
  PanelRightOpen,
  PanelRightClose,
  Eye,
  Crosshair,
} from "lucide-react";

const SEVERITY_COLORS: Record<string, string> = {
  low: "bg-yellow-500",
  medium: "bg-orange-500",
  high: "bg-red-500",
  critical: "bg-red-700",
};

const SEVERITY_RING: Record<string, string> = {
  low: "ring-yellow-500/50",
  medium: "ring-orange-500/50",
  high: "ring-red-500/50",
  critical: "ring-red-700/50",
};

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const surveyId = Number(params.id);
  const [, navigate] = useLocation();
  const [currentImageIdx, setCurrentImageIdx] = useState(0);
  const [sensitivity, setSensitivity] = useState<number>(2.0);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [addingSpot, setAddingSpot] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [highlightedSpotId, setHighlightedSpotId] = useState<number | null>(null);
  const imageContainerRef = useRef<HTMLDivElement>(null);

  const { data: survey } = useQuery({
    queryKey: ["/api/surveys", surveyId],
    queryFn: () => getSurvey(surveyId),
  });

  const { data: images = [] } = useQuery({
    queryKey: ["/api/surveys", surveyId, "images"],
    queryFn: () => getImages(surveyId),
  });

  const { data: spots = [] } = useQuery({
    queryKey: ["/api/surveys", surveyId, "spots"],
    queryFn: () => getSpots(surveyId),
  });

  const currentImage = images[currentImageIdx];
  const imageSpots = spots.filter((s) => currentImage && s.imageId === currentImage.id);

  // ── Sensitivity slider and reprocess ─────────────────────────

  const reprocessMutation = useMutation({
    mutationFn: async (newSensitivity: number) => {
      setIsReprocessing(true);
      return reprocessSurvey(surveyId, newSensitivity);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "spots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "images"] });
      setIsReprocessing(false);
    },
    onError: () => setIsReprocessing(false),
  });

  // ── Spot editing ─────────────────────────────────────────────

  const updateSpotMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Spot> }) => updateSpot(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "spots"] });
    },
  });

  const deleteSpotMutation = useMutation({
    mutationFn: deleteSpot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "spots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "images"] });
    },
  });

  const addSpotMutation = useMutation({
    mutationFn: (data: Partial<Spot>) => addSpot(surveyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "spots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "images"] });
      setAddingSpot(false);
    },
  });

  // ── Click-to-add on image ────────────────────────────────────

  const handleImageClick = useCallback(
    (e: React.MouseEvent<HTMLImageElement>) => {
      if (!addingSpot || !currentImage) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const scaleX = (currentImage.visualWidth || e.currentTarget.naturalWidth) / rect.width;
      const scaleY = (currentImage.visualHeight || e.currentTarget.naturalHeight) / rect.height;
      const pixelX = Math.round((e.clientX - rect.left) * scaleX);
      const pixelY = Math.round((e.clientY - rect.top) * scaleY);

      addSpotMutation.mutate({
        imageId: currentImage.id,
        spotType: "Unknown",
        pixelX,
        pixelY,
        severity: "medium",
      });
    },
    [addingSpot, currentImage, addSpotMutation],
  );

  const handleProceed = () => {
    updateSurvey(surveyId, { status: "editing_notes" });
    navigate(`/notes/${surveyId}`);
  };

  const sensitivityLabel = (val: number) => {
    if (val <= 1.2) return "Very High";
    if (val <= 1.7) return "High";
    if (val <= 2.3) return "Medium";
    if (val <= 2.8) return "Low";
    return "Very Low";
  };

  if (!survey) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header bar */}
      <div className="flex-shrink-0 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-3">
        <div className="flex items-center justify-between max-w-[1920px] mx-auto">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/")} data-testid="button-back">
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div>
              <h1 className="text-base font-bold" data-testid="text-review-title">
                Review Hotspots
              </h1>
              <p className="text-xs text-muted-foreground">
                {survey.propertyAddress || "Unnamed Property"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPanelOpen(!panelOpen)}
              data-testid="button-toggle-panel"
            >
              {panelOpen ? (
                <PanelRightClose className="w-4 h-4 mr-1" />
              ) : (
                <PanelRightOpen className="w-4 h-4 mr-1" />
              )}
              {panelOpen ? "Hide Panel" : "Show Spots"}
            </Button>
            <Button onClick={handleProceed} data-testid="button-proceed">
              Proceed to Notes
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Image viewer — takes all available space */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Sensitivity + image nav bar */}
          <div className="flex-shrink-0 px-4 py-2 border-b bg-muted/30">
            <div className="flex items-center gap-4 max-w-[1920px] mx-auto">
              {/* Image navigation */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setCurrentImageIdx(Math.max(0, currentImageIdx - 1))}
                  disabled={currentImageIdx === 0}
                  data-testid="button-prev-image"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </Button>
                <span className="text-xs font-medium min-w-[100px] text-center">
                  {currentImage?.filename || "—"} ({currentImageIdx + 1}/{images.length})
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setCurrentImageIdx(Math.min(images.length - 1, currentImageIdx + 1))}
                  disabled={currentImageIdx === images.length - 1}
                  data-testid="button-next-image"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>

              {/* Divider */}
              <div className="h-5 w-px bg-border flex-shrink-0" />

              {/* Sensitivity slider */}
              <div className="flex items-center gap-2 flex-1 min-w-0 max-w-md">
                <SlidersHorizontal className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                <span className="text-xs text-muted-foreground flex-shrink-0 w-[70px]">
                  {sensitivityLabel(sensitivity)}
                </span>
                <Slider
                  min={0.5}
                  max={4.0}
                  step={0.1}
                  value={[sensitivity]}
                  onValueChange={([v]) => setSensitivity(v)}
                  className="flex-1"
                  data-testid="slider-sensitivity"
                />
                <span className="text-xs text-muted-foreground flex-shrink-0 w-[30px]">{sensitivity.toFixed(1)}σ</span>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => reprocessMutation.mutate(sensitivity)}
                  disabled={isReprocessing}
                  data-testid="button-reprocess"
                >
                  {isReprocessing ? (
                    <Loader2 className="w-3 h-3 animate-spin mr-1" />
                  ) : (
                    <RefreshCw className="w-3 h-3 mr-1" />
                  )}
                  Reprocess
                </Button>
              </div>

              {/* Divider */}
              <div className="h-5 w-px bg-border flex-shrink-0" />

              {/* Add spot button */}
              <Button
                variant={addingSpot ? "default" : "outline"}
                size="sm"
                className="h-7 text-xs flex-shrink-0"
                onClick={() => setAddingSpot(!addingSpot)}
                data-testid="button-add-spot"
              >
                {addingSpot ? (
                  <>
                    <Crosshair className="w-3 h-3 mr-1" />
                    Click image to place...
                  </>
                ) : (
                  <>
                    <Plus className="w-3 h-3 mr-1" />
                    Add Spot
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Thermal image — fills remaining space */}
          <div
            ref={imageContainerRef}
            className="flex-1 overflow-auto flex items-center justify-center bg-black/5 p-4"
          >
            {currentImage && (
              <div className="relative max-w-full max-h-full">
                <img
                  src={
                    currentImage.labeledPath
                      ? `${API_BASE}/api/images/${currentImage.id}/labeled?t=${Date.now()}`
                      : `${API_BASE}/api/images/${currentImage.id}/file`
                  }
                  alt={currentImage.filename}
                  className={`max-w-full max-h-[calc(100vh-180px)] object-contain rounded shadow-lg ${addingSpot ? "cursor-crosshair" : ""}`}
                  onClick={handleImageClick}
                  data-testid="img-thermal"
                />
                {/* Spot overlay markers */}
                {currentImage && imageSpots.map((spot) => {
                  const imgEl = imageContainerRef.current?.querySelector("img");
                  if (!imgEl) return null;
                  const naturalW = currentImage.visualWidth || imgEl.naturalWidth;
                  const naturalH = currentImage.visualHeight || imgEl.naturalHeight;
                  const displayW = imgEl.clientWidth;
                  const displayH = imgEl.clientHeight;
                  if (!naturalW || !naturalH || !displayW || !displayH) return null;
                  const left = (spot.pixelX / naturalW) * 100;
                  const top = (spot.pixelY / naturalH) * 100;
                  const isHighlighted = highlightedSpotId === spot.id;
                  return (
                    <div
                      key={spot.id}
                      className={`absolute w-5 h-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white flex items-center justify-center text-[8px] font-bold text-white shadow-md transition-all ${
                        SEVERITY_COLORS[spot.severity]
                      } ${isHighlighted ? "ring-4 ring-white scale-150 z-10" : "z-5"}`}
                      style={{ left: `${left}%`, top: `${top}%` }}
                      title={`#${spot.spotNumber} ${spot.spotType}`}
                      onMouseEnter={() => setHighlightedSpotId(spot.id)}
                      onMouseLeave={() => setHighlightedSpotId(null)}
                    >
                      {spot.spotNumber}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Thermal stats bar */}
          {currentImage && currentImage.minTemp !== null && (
            <div className="flex-shrink-0 px-4 py-1.5 border-t bg-muted/20 text-xs text-muted-foreground text-center">
              Thermal range: {currentImage.minTemp?.toFixed(2)} – {currentImage.maxTemp?.toFixed(2)} (relative)
              {" · "}Mean: {currentImage.meanTemp?.toFixed(2)} · Std: {currentImage.stdTemp?.toFixed(2)}
              {" · "}{imageSpots.length} spot{imageSpots.length !== 1 ? "s" : ""} on this image
            </div>
          )}
        </div>

        {/* Spot editor panel — collapsible sidebar */}
        {panelOpen && (
          <div className="w-80 flex-shrink-0 border-l bg-background flex flex-col overflow-hidden">
            <div className="flex-shrink-0 px-3 py-2 border-b">
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Spots on this image ({imageSpots.length})
              </h2>
            </div>

            <ScrollArea className="flex-1">
              <div className="p-3 space-y-2">
                {imageSpots.length === 0 && (
                  <p className="text-xs text-muted-foreground py-4 text-center">
                    No hotspots detected. Try reducing sensitivity or add spots manually.
                  </p>
                )}

                {imageSpots.map((spot) => (
                  <SpotEditor
                    key={spot.id}
                    spot={spot}
                    isHighlighted={highlightedSpotId === spot.id}
                    onUpdate={(data) =>
                      updateSpotMutation.mutate({ id: spot.id, data })
                    }
                    onDelete={() => deleteSpotMutation.mutate(spot.id)}
                    onHover={(id) => setHighlightedSpotId(id)}
                  />
                ))}

                {/* All spots across survey */}
                {spots.length > imageSpots.length && (
                  <>
                    <div className="pt-3 pb-1">
                      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Other images ({spots.length - imageSpots.length})
                      </h2>
                    </div>
                    {spots
                      .filter((s) => !currentImage || s.imageId !== currentImage.id)
                      .map((spot) => {
                        const img = images.find((i) => i.id === spot.imageId);
                        return (
                          <div key={spot.id} className="opacity-50">
                            <Card>
                              <CardContent className="py-1.5 px-2.5">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1.5">
                                    <span className={`w-2 h-2 rounded-full ${SEVERITY_COLORS[spot.severity]}`} />
                                    <span className="text-xs font-medium">#{spot.spotNumber}</span>
                                    <span className="text-xs text-muted-foreground">{spot.spotType}</span>
                                  </div>
                                  <span className="text-[10px] text-muted-foreground truncate max-w-[80px]">{img?.filename}</span>
                                </div>
                              </CardContent>
                            </Card>
                          </div>
                        );
                      })}
                  </>
                )}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  );
}

function SpotEditor({
  spot,
  isHighlighted,
  onUpdate,
  onDelete,
  onHover,
}: {
  spot: Spot;
  isHighlighted: boolean;
  onUpdate: (data: Partial<Spot>) => void;
  onDelete: () => void;
  onHover: (id: number | null) => void;
}) {
  return (
    <Card
      className={`transition-all ${isHighlighted ? "ring-2 ring-primary shadow-md" : ""}`}
      data-testid={`card-spot-${spot.id}`}
      onMouseEnter={() => onHover(spot.id)}
      onMouseLeave={() => onHover(null)}
    >
      <CardContent className="py-2 px-3 space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${SEVERITY_COLORS[spot.severity]}`} />
            <span className="font-medium text-xs">#{spot.spotNumber}</span>
            {spot.isAutoDetected ? (
              <Badge variant="outline" className="text-[9px] py-0 h-4">auto</Badge>
            ) : (
              <Badge variant="secondary" className="text-[9px] py-0 h-4">manual</Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5"
            onClick={onDelete}
            data-testid={`button-delete-spot-${spot.id}`}
          >
            <Trash2 className="w-2.5 h-2.5 text-muted-foreground" />
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-1.5">
          <div>
            <Label className="text-[10px] text-muted-foreground">Type</Label>
            <Select
              value={spot.spotType}
              onValueChange={(v) => onUpdate({ spotType: v })}
            >
              <SelectTrigger className="h-7 text-xs" data-testid={`select-type-${spot.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SPOT_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[10px] text-muted-foreground">Number</Label>
            <Input
              type="number"
              className="h-7 text-xs"
              value={spot.spotNumber}
              onChange={(e) => onUpdate({ spotNumber: parseInt(e.target.value) || 1 })}
              min={1}
              data-testid={`input-number-${spot.id}`}
            />
          </div>
        </div>

        {spot.temperature !== null && (
          <p className="text-[10px] text-muted-foreground">
            Value: {spot.temperature.toFixed(3)} · {spot.severity}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
