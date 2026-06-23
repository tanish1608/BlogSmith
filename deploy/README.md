# Deploying BlogSmith on Google Cloud

Two Cloud Run surfaces talk to one Firebase project:

- **`blogsmith-api`** (Cloud Run *Service*) — always-on API + dashboard. Dispatches runs.
- **`blogsmith-job`** (Cloud Run *Job*) — executes one run's Phase A (discovery → email gate), then exits.

Plus **Firestore + Firebase Auth + Storage** (the central project) and **one Cloud Scheduler cron** that fans out scheduled blogs.

## 1. One-time setup

```bash
PROJECT=your-project
REGION=us-central1
gcloud config set project $PROJECT

# Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  firestore.googleapis.com firebasestorage.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com

# Secrets (generate strong values)
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())" \
  | gcloud secrets create blogsmith-enc-key --data-file=-
printf '%s' "$(openssl rand -hex 32)" | gcloud secrets create blogsmith-scheduler-secret --data-file=-

# Firestore + Storage rules
firebase deploy --only firestore:rules,storage:rules
```

Create users in the **Firebase console → Authentication**. They sign in via the dashboard and add their own Gemini key under Settings.

## 2. Deploy

```bash
gcloud builds submit --config deploy/cloudbuild.api.yaml --substitutions=_REGION=$REGION
gcloud builds submit --config deploy/cloudbuild.job.yaml --substitutions=_REGION=$REGION
```

## 3. Scheduler

One cron that fans out to every due site (every 15 min):

```bash
API_URL=$(gcloud run services describe blogsmith-api --region=$REGION --format='value(status.url)')
SECRET=$(gcloud secrets versions access latest --secret=blogsmith-scheduler-secret)
gcloud scheduler jobs create http blogsmith-tick \
  --location=$REGION --schedule="*/15 * * * *" \
  --uri="$API_URL/scheduler/tick" --http-method=POST \
  --headers="X-Scheduler-Secret=$SECRET"
```

## 4. Grant the API permission to run the Job

```bash
SA=$(gcloud run services describe blogsmith-api --region=$REGION --format='value(spec.template.spec.serviceAccountName)')
gcloud run jobs add-iam-policy-binding blogsmith-job --region=$REGION \
  --member="serviceAccount:$SA" --role="roles/run.invoker"
```

Notes:
- The API runs runs as Cloud Run Jobs because `DISPATCH_TO_CLOUD_RUN=true` is set in the API build.
- Application-default credentials cover Firestore/Storage; no service-account JSON is baked into images.
