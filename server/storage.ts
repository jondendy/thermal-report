import { surveys, images, spots, assessorNotes, type Survey, type InsertSurvey, type Image, type InsertImage, type Spot, type InsertSpot, type AssessorNote, type InsertAssessorNote } from "@shared/schema";
import { drizzle } from "drizzle-orm/better-sqlite3";
import Database from "better-sqlite3";
import { eq, and, asc, desc } from "drizzle-orm";

const sqlite = new Database("data.db");
const db = drizzle(sqlite);

export interface IStorage {
  // Surveys
  createSurvey(data: InsertSurvey): Survey;
  getSurvey(id: number): Survey | undefined;
  getAllSurveys(): Survey[];
  updateSurvey(id: number, data: Partial<InsertSurvey>): Survey | undefined;
  deleteSurvey(id: number): void;

  // Images
  createImage(data: InsertImage): Image;
  getImage(id: number): Image | undefined;
  getImagesBySurvey(surveyId: number): Image[];
  updateImage(id: number, data: Partial<InsertImage>): Image | undefined;

  // Spots
  createSpot(data: InsertSpot): Spot;
  getSpot(id: number): Spot | undefined;
  getSpotsBySurvey(surveyId: number): Spot[];
  getSpotsByImage(imageId: number): Spot[];
  updateSpot(id: number, data: Partial<InsertSpot>): Spot | undefined;
  deleteSpotsBySurvey(surveyId: number): void;
  getNextSpotNumber(surveyId: number): number;

  // Assessor Notes
  createOrUpdateNote(data: InsertAssessorNote): AssessorNote;
  getNotesBySurvey(surveyId: number): AssessorNote[];
  getNote(surveyId: number, spotNumber: number): AssessorNote | undefined;
}

export class DatabaseStorage implements IStorage {
  createSurvey(data: InsertSurvey): Survey {
    return db.insert(surveys).values(data).returning().get();
  }

  getSurvey(id: number): Survey | undefined {
    return db.select().from(surveys).where(eq(surveys.id, id)).get();
  }

  getAllSurveys(): Survey[] {
    return db.select().from(surveys).orderBy(desc(surveys.createdAt)).all();
  }

  updateSurvey(id: number, data: Partial<InsertSurvey>): Survey | undefined {
    return db.update(surveys).set(data).where(eq(surveys.id, id)).returning().get();
  }

  deleteSurvey(id: number): void {
    db.delete(assessorNotes).where(eq(assessorNotes.surveyId, id)).run();
    db.delete(spots).where(eq(spots.surveyId, id)).run();
    db.delete(images).where(eq(images.surveyId, id)).run();
    db.delete(surveys).where(eq(surveys.id, id)).run();
  }

  createImage(data: InsertImage): Image {
    return db.insert(images).values(data).returning().get();
  }

  getImage(id: number): Image | undefined {
    return db.select().from(images).where(eq(images.id, id)).get();
  }

  getImagesBySurvey(surveyId: number): Image[] {
    return db.select().from(images).where(eq(images.surveyId, surveyId)).all();
  }

  updateImage(id: number, data: Partial<InsertImage>): Image | undefined {
    return db.update(images).set(data).where(eq(images.id, id)).returning().get();
  }

  createSpot(data: InsertSpot): Spot {
    return db.insert(spots).values(data).returning().get();
  }

  getSpot(id: number): Spot | undefined {
    return db.select().from(spots).where(eq(spots.id, id)).get();
  }

  getSpotsBySurvey(surveyId: number): Spot[] {
    return db.select().from(spots)
      .where(and(eq(spots.surveyId, surveyId), eq(spots.isDeleted, 0)))
      .orderBy(asc(spots.spotNumber))
      .all();
  }

  getSpotsByImage(imageId: number): Spot[] {
    return db.select().from(spots)
      .where(and(eq(spots.imageId, imageId), eq(spots.isDeleted, 0)))
      .orderBy(asc(spots.spotNumber))
      .all();
  }

  updateSpot(id: number, data: Partial<InsertSpot>): Spot | undefined {
    return db.update(spots).set(data).where(eq(spots.id, id)).returning().get();
  }

  deleteSpotsBySurvey(surveyId: number): void {
    db.delete(spots).where(eq(spots.surveyId, surveyId)).run();
  }

  getNextSpotNumber(surveyId: number): number {
    const existing = db.select().from(spots)
      .where(and(eq(spots.surveyId, surveyId), eq(spots.isDeleted, 0)))
      .orderBy(desc(spots.spotNumber))
      .get();
    return existing ? existing.spotNumber + 1 : 1;
  }

  createOrUpdateNote(data: InsertAssessorNote): AssessorNote {
    const existing = db.select().from(assessorNotes)
      .where(and(
        eq(assessorNotes.surveyId, data.surveyId),
        eq(assessorNotes.spotNumber, data.spotNumber)
      ))
      .get();
    
    if (existing) {
      return db.update(assessorNotes)
        .set({ note: data.note, removedRecommendations: data.removedRecommendations })
        .where(eq(assessorNotes.id, existing.id))
        .returning().get();
    }
    return db.insert(assessorNotes).values(data).returning().get();
  }

  getNotesBySurvey(surveyId: number): AssessorNote[] {
    return db.select().from(assessorNotes)
      .where(eq(assessorNotes.surveyId, surveyId))
      .all();
  }

  getNote(surveyId: number, spotNumber: number): AssessorNote | undefined {
    return db.select().from(assessorNotes)
      .where(and(
        eq(assessorNotes.surveyId, surveyId),
        eq(assessorNotes.spotNumber, spotNumber)
      ))
      .get();
  }
}

export const storage = new DatabaseStorage();
