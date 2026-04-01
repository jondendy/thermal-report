import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// A survey is a batch of thermal images for one property
export const surveys = sqliteTable("surveys", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  propertyAddress: text("property_address").notNull().default(""),
  inspectorName: text("inspector_name").notNull().default(""),
  sensitivity: real("sensitivity").notNull().default(2.0), // std dev multiplier
  status: text("status").notNull().default("uploading"), // uploading | reviewing | editing_notes | complete
  createdAt: text("created_at").notNull(),
});

// Each uploaded thermal image
export const images = sqliteTable("images", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  surveyId: integer("survey_id").notNull(),
  filename: text("filename").notNull(),
  originalPath: text("original_path").notNull(),
  labeledPath: text("labeled_path").default(""),
  thermalDataPath: text("thermal_data_path").default(""),
  minTemp: real("min_temp"),
  maxTemp: real("max_temp"),
  meanTemp: real("mean_temp"),
  medianTemp: real("median_temp"),
  stdTemp: real("std_temp"),
  thermalWidth: integer("thermal_width"),
  thermalHeight: integer("thermal_height"),
  visualWidth: integer("visual_width"),
  visualHeight: integer("visual_height"),
});

// Each detected or manually-added hotspot
export const spots = sqliteTable("spots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  surveyId: integer("survey_id").notNull(),
  imageId: integer("image_id").notNull(),
  spotNumber: integer("spot_number").notNull(), // user-facing number
  spotType: text("spot_type").notNull().default("Unknown"), // Window, Door, Wall, Roof, etc.
  temperature: real("temperature"),
  severity: text("severity").notNull().default("medium"), // low, medium, high, critical
  pixelX: integer("pixel_x").notNull(), // position on the visual image
  pixelY: integer("pixel_y").notNull(),
  areaSize: integer("area_size").default(0),
  isAutoDetected: integer("is_auto_detected").notNull().default(1), // 1=auto, 0=manual
  isDeleted: integer("is_deleted").notNull().default(0), // soft delete
});

// Assessor notes per finding (grouped by spot type + number)
export const assessorNotes = sqliteTable("assessor_notes", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  surveyId: integer("survey_id").notNull(),
  spotNumber: integer("spot_number").notNull(),
  note: text("note").notNull().default(""),
  removedRecommendations: text("removed_recommendations").notNull().default("[]"), // JSON array of recommendation indices
});

// Insert schemas
export const insertSurveySchema = createInsertSchema(surveys).omit({ id: true });
export const insertImageSchema = createInsertSchema(images).omit({ id: true });
export const insertSpotSchema = createInsertSchema(spots).omit({ id: true });
export const insertAssessorNoteSchema = createInsertSchema(assessorNotes).omit({ id: true });

// Types
export type Survey = typeof surveys.$inferSelect;
export type InsertSurvey = z.infer<typeof insertSurveySchema>;
export type Image = typeof images.$inferSelect;
export type InsertImage = z.infer<typeof insertImageSchema>;
export type Spot = typeof spots.$inferSelect;
export type InsertSpot = z.infer<typeof insertSpotSchema>;
export type AssessorNote = typeof assessorNotes.$inferSelect;
export type InsertAssessorNote = z.infer<typeof insertAssessorNoteSchema>;

// Spot type options
export const SPOT_TYPES = [
  "Unknown", "Window", "Door", "Wall", "Roof", "Eaves", "Chimney", "Vent", "Porch", "Floor", "Pipe", "Other"
] as const;

export type SpotType = typeof SPOT_TYPES[number];
