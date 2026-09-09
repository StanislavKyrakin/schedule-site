param(
  [Parameter(Mandatory=$true)][string]$ProjectId,
  [Parameter(Mandatory=$true)][string]$SpreadsheetId,
  [string]$Region = "europe-west1",
  [string]$Service = "schedule-site"
)

gcloud config set project $ProjectId

gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  sheets.googleapis.com

gcloud iam service-accounts create schedule-site `
  --project $ProjectId `
  --display-name="Schedule Site runtime" 2>$null

$RuntimeSa = "schedule-site@$ProjectId.iam.gserviceaccount.com"

gcloud run deploy $Service `
  --source . `
  --region $Region `
  --service-account $RuntimeSa `
  --allow-unauthenticated `
  --set-env-vars "SPREADSHEET_ID=$SpreadsheetId,SHEETS_CACHE_SECONDS=30"
