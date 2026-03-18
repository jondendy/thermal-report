# Deploying to Cloud Run via Cloud Build

All deployment happens inside GCP — no GitHub Actions, no credentials outside Google.

## One-time GCP setup

### 1. Create the Artifact Registry repository
```bash
gcloud artifacts repositories create thermal-report \
  --repository-format=docker \
  --location=us-central1 \
  --project=sc-thermal-project
```

### 2. Grant Cloud Build the minimum IAM roles it needs
```bash
PROJECT_NUMBER=$(gcloud projects describe sc-thermal-project --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:${CB_SA}" --role="roles/run.admin"

gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:${CB_SA}" --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:${CB_SA}" --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:${CB_SA}" --role="roles/secretmanager.secretAccessor"
```
> These are the **minimum roles** needed. Do not grant Owner or Editor to the build SA.

### 3. Store secrets in Secret Manager (replaces your .env file)
```bash
# Your Google Drive service account JSON
gcloud secrets create GOOGLE_DRIVE_CREDENTIALS \
  --data-file=service_account.json \
  --project=sc-thermal-project

# Flask secret key
echo -n "your-secret-key-here" | gcloud secrets create FLASK_SECRET_KEY \
  --data-file=- \
  --project=sc-thermal-project

# Add any other values from your .env the same way
```

### 4. Create a Cloud Storage bucket for uploads and reports
```bash
gcloud storage buckets create gs://sc-thermal-data \
  --location=us-central1 \
  --project=sc-thermal-project
```
This replaces local `upload/` and `reports/` directories so data persists
across Cloud Run revisions.

### 5. Connect your GitHub repo to Cloud Build
1. GCP Console → Cloud Build → Triggers → **Connect Repository**
2. Select GitHub, authenticate, choose `jondendy/thermal-report`
3. Create trigger:
   - **Event**: Push to branch
   - **Branch**: `^main$`
   - **Config**: Cloud Build configuration file — `cloudbuild.yaml`
4. Save.

---

## Every deploy after that

```bash
git push origin main
```

Cloud Build picks it up automatically:
```
Build image → Push to Artifact Registry → Deploy to Cloud Run
```
Zero-downtime rollout. Your team's URL never changes.

---

## Your team's URL

After the first deploy, get the URL:
```bash
gcloud run services describe thermal-report \
  --region=us-central1 \
  --project=sc-thermal-project \
  --format='value(status.url)'
```
It will look like:
```
https://thermal-report-xxxxxxxxxxxx-uc.a.run.app
```
Share that with the team. It's HTTPS, Google-managed certificate, permanent.

---

## Tightening your IAM (addressing over-entitled user)

Your personal account should not need Owner on this project day-to-day.
Create a least-privilege setup:

```bash
# Create a dedicated service account for the app itself
gcloud iam service-accounts create thermal-app-sa \
  --display-name="Thermal Report App" \
  --project=sc-thermal-project

# Grant it only what it needs
gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:thermal-app-sa@sc-thermal-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding sc-thermal-project \
  --member="serviceAccount:thermal-app-sa@sc-thermal-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Attach it to the Cloud Run service
gcloud run services update thermal-report \
  --service-account=thermal-app-sa@sc-thermal-project.iam.gserviceaccount.com \
  --region=us-central1
```

Then reduce your own account from Owner to **Editor** or a custom role —
Google Security Insights will stop flagging you.
