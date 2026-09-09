#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Укажите PROJECT_ID}"
SPREADSHEET_ID="${2:?Укажите SPREADSHEET_ID}"
REGION="${3:-europe-west1}"
SERVICE="${4:-schedule-site}"
RUNTIME_SA="${5:-schedule-site@${PROJECT_ID}.iam.gserviceaccount.com}"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sheets.googleapis.com

gcloud iam service-accounts create schedule-site \
  --project "$PROJECT_ID" \
  --display-name="Schedule Site runtime" \
  2>/dev/null || true

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --allow-unauthenticated \
  --set-env-vars "SPREADSHEET_ID=$SPREADSHEET_ID,SHEETS_CACHE_SECONDS=30"
