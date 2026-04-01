import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useParams, useLocation } from "wouter";
import { queryClient } from "@/lib/queryClient";
import {
  getSurvey,
  getSpots,
  getNotes,
  saveNote,
  getRecommendations,
  generatePdf,
  updateSurvey,
  getImages,
} from "@/lib/api";
import type { Spot, AssessorNote, Recommendations } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  FileDown,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Pencil,
} from "lucide-react";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"];

export default function NotesPage() {
  const params = useParams<{ id: string }>();
  const surveyId = Number(params.id);
  const [, navigate] = useLocation();
  const [generating, setGenerating] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  const { data: survey } = useQuery({
    queryKey: ["/api/surveys", surveyId],
    queryFn: () => getSurvey(surveyId),
  });

  const { data: spots = [] } = useQuery({
    queryKey: ["/api/surveys", surveyId, "spots"],
    queryFn: () => getSpots(surveyId),
  });

  const { data: images = [] } = useQuery({
    queryKey: ["/api/surveys", surveyId, "images"],
    queryFn: () => getImages(surveyId),
  });

  const { data: existingNotes = [] } = useQuery({
    queryKey: ["/api/surveys", surveyId, "notes"],
    queryFn: () => getNotes(surveyId),
  });

  const { data: recommendations = {} } = useQuery<Recommendations>({
    queryKey: ["/api/recommendations"],
    queryFn: getRecommendations,
  });

  // Group spots by type+number for findings
  const findings = groupSpotsByNumber(spots);

  const generateMutation = useMutation({
    mutationFn: async () => {
      setGenerating(true);
      // Update survey metadata
      await updateSurvey(surveyId, {
        propertyAddress: survey?.propertyAddress,
        inspectorName: survey?.inspectorName,
      });
      return generatePdf(surveyId);
    },
    onSuccess: (result) => {
      setGenerating(false);
      if (result.filename) {
        setPdfUrl(`/api/reports/${result.filename}`);
      }
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId] });
    },
    onError: () => setGenerating(false),
  });

  if (!survey) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/review/${surveyId}`)} data-testid="button-back">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold" data-testid="text-notes-title">
              Notes & Report
            </h1>
            <p className="text-xs text-muted-foreground">
              {survey.propertyAddress || "Unnamed Property"}
            </p>
          </div>
        </div>
      </div>

      {/* Survey metadata */}
      <Card className="mb-6">
        <CardContent className="py-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-xs">Property Address</Label>
              <Input
                value={survey.propertyAddress}
                onChange={(e) =>
                  queryClient.setQueryData(["/api/surveys", surveyId], {
                    ...survey,
                    propertyAddress: e.target.value,
                  })
                }
                onBlur={(e) => updateSurvey(surveyId, { propertyAddress: e.target.value })}
                data-testid="input-address"
              />
            </div>
            <div>
              <Label className="text-xs">Surveyor Name</Label>
              <Input
                value={survey.inspectorName}
                onChange={(e) =>
                  queryClient.setQueryData(["/api/surveys", surveyId], {
                    ...survey,
                    inspectorName: e.target.value,
                  })
                }
                onBlur={(e) => updateSurvey(surveyId, { inspectorName: e.target.value })}
                data-testid="input-inspector"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold">{images.length}</div>
              <div className="text-xs text-muted-foreground">Images</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{spots.length}</div>
              <div className="text-xs text-muted-foreground">Hotspots</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-600">
                {spots.filter((s) => s.severity === "critical" || s.severity === "high").length}
              </div>
              <div className="text-xs text-muted-foreground">High Priority</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{Object.keys(findings).length}</div>
              <div className="text-xs text-muted-foreground">Findings</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Findings with notes */}
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Findings & Recommendations
      </h2>

      {Object.entries(findings)
        .sort(([, a], [, b]) => {
          const ai = SEVERITY_ORDER.indexOf(a.severity);
          const bi = SEVERITY_ORDER.indexOf(b.severity);
          return ai - bi;
        })
        .map(([key, finding]) => (
          <FindingEditor
            key={key}
            finding={finding}
            surveyId={surveyId}
            existingNote={existingNotes.find((n) => n.spotNumber === finding.spotNumber)}
            recommendations={recommendations}
          />
        ))}

      {/* Generate PDF */}
      <Card className="mt-6">
        <CardContent className="py-6 text-center space-y-3">
          <p className="text-sm text-muted-foreground">
            When you are happy with the spot labels, notes, and recommendations, generate the PDF report.
          </p>
          <Button
            size="lg"
            onClick={() => generateMutation.mutate()}
            disabled={generating}
            data-testid="button-generate-pdf"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating PDF...
              </>
            ) : (
              <>
                <FileDown className="w-4 h-4 mr-2" />
                Generate PDF Report
              </>
            )}
          </Button>

          {pdfUrl && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary underline"
                data-testid="link-download-pdf"
              >
                Download Report PDF
              </a>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Group spots by spotNumber
interface Finding {
  spotNumber: number;
  spotType: string;
  severity: string;
  spots: Spot[];
}

function groupSpotsByNumber(spots: Spot[]): Record<number, Finding> {
  const grouped: Record<number, Finding> = {};
  for (const spot of spots) {
    if (!grouped[spot.spotNumber]) {
      grouped[spot.spotNumber] = {
        spotNumber: spot.spotNumber,
        spotType: spot.spotType,
        severity: spot.severity,
        spots: [],
      };
    }
    grouped[spot.spotNumber].spots.push(spot);
    // Use highest severity
    const current = grouped[spot.spotNumber];
    if (SEVERITY_ORDER.indexOf(spot.severity) < SEVERITY_ORDER.indexOf(current.severity)) {
      current.severity = spot.severity;
    }
    if (spot.spotType !== "Unknown") {
      current.spotType = spot.spotType;
    }
  }
  return grouped;
}

function FindingEditor({
  finding,
  surveyId,
  existingNote,
  recommendations,
}: {
  finding: Finding;
  surveyId: number;
  existingNote?: AssessorNote;
  recommendations: Recommendations;
}) {
  const [note, setNote] = useState(existingNote?.note || "");
  const [removedRecs, setRemovedRecs] = useState<number[]>(() => {
    try {
      return JSON.parse(existingNote?.removedRecommendations || "[]");
    } catch {
      return [];
    }
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setNote(existingNote?.note || "");
    try {
      setRemovedRecs(JSON.parse(existingNote?.removedRecommendations || "[]"));
    } catch {
      setRemovedRecs([]);
    }
  }, [existingNote]);

  const saveMutation = useMutation({
    mutationFn: () => {
      setSaving(true);
      return saveNote(surveyId, finding.spotNumber, note, removedRecs);
    },
    onSuccess: () => {
      setSaving(false);
      queryClient.invalidateQueries({ queryKey: ["/api/surveys", surveyId, "notes"] });
    },
    onError: () => setSaving(false),
  });

  const rec = recommendations[finding.spotType];
  const advice: string[] = rec?.advice || [];

  const severityColor: Record<string, string> = {
    critical: "text-red-700",
    high: "text-red-500",
    medium: "text-orange-500",
    low: "text-yellow-600",
  };

  const toggleRec = (idx: number) => {
    const newRemoved = removedRecs.includes(idx)
      ? removedRecs.filter((i) => i !== idx)
      : [...removedRecs, idx];
    setRemovedRecs(newRemoved);
  };

  return (
    <Card className="mb-4" data-testid={`card-finding-${finding.spotNumber}`}>
      <CardContent className="py-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`w-4 h-4 ${severityColor[finding.severity]}`} />
            <span className="font-medium text-sm">
              #{finding.spotNumber} — {finding.spotType}
            </span>
            <Badge
              variant={
                finding.severity === "critical" || finding.severity === "high"
                  ? "destructive"
                  : "secondary"
              }
            >
              {finding.severity}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            {finding.spots.length} spot(s)
          </span>
        </div>

        {/* Type description */}
        {rec?.description && (
          <p className="text-xs text-muted-foreground">{rec.description}</p>
        )}

        {/* Recommendations with checkboxes */}
        {advice.length > 0 && (
          <div>
            <Label className="text-xs font-medium">Recommendations</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Uncheck any recommendations that are not appropriate for this property.
            </p>
            <div className="space-y-1">
              {advice.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <Checkbox
                    checked={!removedRecs.includes(idx)}
                    onCheckedChange={() => toggleRec(idx)}
                    className="mt-0.5"
                    data-testid={`checkbox-rec-${finding.spotNumber}-${idx}`}
                  />
                  <span
                    className={`text-xs ${removedRecs.includes(idx) ? "line-through text-muted-foreground" : ""}`}
                  >
                    {item}
                  </span>
                </div>
              ))}
            </div>
            {rec?.savings && (
              <p className="text-xs text-primary mt-1">Estimated savings: {rec.savings}</p>
            )}
          </div>
        )}

        {/* Assessor note */}
        <div>
          <Label className="text-xs font-medium flex items-center gap-1">
            <Pencil className="w-3 h-3" />
            Assessor Note
          </Label>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add your observations, corrections, or additional context for this finding..."
            className="text-xs mt-1"
            rows={2}
            data-testid={`textarea-note-${finding.spotNumber}`}
          />
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => saveMutation.mutate()}
          disabled={saving}
          data-testid={`button-save-note-${finding.spotNumber}`}
        >
          {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
          Save Note
        </Button>
      </CardContent>
    </Card>
  );
}
