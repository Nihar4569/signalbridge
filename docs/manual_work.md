# manual_work.md — Things a human must do

Some setup **cannot be done by code** — it needs a person clicking in the Google
Cloud / Firebase console, creating accounts, or holding secret keys. This file
lists all of it in one place, in order.

The base project runs **without any of this** (local fixtures). You only need
these steps when you want to use Gemini, Firestore, or deploy to the cloud.

Legend: 🟢 easy · 🟡 some care · 🔴 do carefully (money / security)

---

## 1. Get a Gemini API key 🟢 (needed to run the agent)

1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**. Copy it.
3. In the project, put it in your local `.env` file:
   ```
   GOOGLE_API_KEY=paste_key_here
   ```
4. **Never commit `.env`.** It is already in `.gitignore`.

That's enough to run `adk run backend/agent`.

---

## 2. Create a Google Cloud project 🟡 (needed for Firestore + deploy)

1. Go to <https://console.cloud.google.com/>.
2. Top bar → **Create project**. Give it a name (e.g. `signalbridge-demo`).
3. Note the **Project ID** (looks like `signalbridge-demo-470213`).
4. Put it in `.env`:
   ```
   GOOGLE_CLOUD_PROJECT=your-project-id
   ```
5. 🔴 **Enable billing** for the project (Billing → link a billing account).
   Firestore and Cloud Run have free tiers, but the project must have billing on.
   Set a **budget alert** (Billing → Budgets) so there are no surprises.

---

## 3. Set up Firestore 🟡

1. In the console, open **Firestore**.
2. Click **Create database** → **Native mode** (not Datastore mode).
3. Pick a region close to you (e.g. `asia-south1` for Mumbai). **This is permanent.**
4. Install the gcloud CLI (<https://cloud.google.com/sdk/docs/install>) and log in:
   ```bash
   gcloud auth application-default login
   gcloud config set project your-project-id
   ```
5. Seed the demo data from our fixtures:
   ```bash
   # make sure .env has GOOGLE_CLOUD_PROJECT set first
   python -m scripts.seed_firestore
   ```
6. Switch the app to Firestore by editing `.env`:
   ```
   DATA_BACKEND=firestore
   ```

> Want to test Firestore without touching the cloud? Install the **Firestore
> emulator** (`gcloud components install cloud-firestore-emulator`), run it, and
> set `FIRESTORE_EMULATOR_HOST=localhost:8080` in `.env`.
>
> `FirestoreStore` lives in `backend/core/store.py`. After seeding:
> ```
> DATA_BACKEND=firestore
> GOOGLE_CLOUD_PROJECT=your-project-id
> TENANT_ID=buildx-demo
> ```
> Validate fixtures without writing: `python -m scripts.seed_firestore --dry-run`
> Deploy rules/indexes: `firebase deploy --only firestore`

---

## 4. Set up Firebase (Auth + Hosting) 🟡

1. Go to <https://console.firebase.google.com/> and **Add project** — choose the
   **same** Google Cloud project you made in step 2.
2. **Authentication** → Get started → enable **Email/Password** (and **Anonymous**
   for easy demo logins).
3. **Hosting** → Get started (this is where the dashboard will live later).
4. Install the Firebase CLI and log in:
   ```bash
   npm install -g firebase-tools
   firebase login
   firebase init        # choose Hosting + Firestore when the frontend exists
   ```

---

## 5. Deploy to Cloud Run 🔴 (for the live demo)

Do this only once the app works locally.

1. Enable the APIs:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
       firestore.googleapis.com secretmanager.googleapis.com
   ```
2. Store the Gemini key as a secret (do **not** bake it into the image):
   ```bash
   printf "YOUR_KEY" | gcloud secrets create gemini-api-key --data-file=-
   ```
3. Deploy the API:
   ```bash
   gcloud run deploy signalbridge-api \
     --source . \
     --region asia-south1 \
     --set-secrets GOOGLE_API_KEY=gemini-api-key:latest \
     --set-env-vars DATA_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=your-project-id
   ```
4. The API scans weather and news itself while the process is running
   (every 2 minutes). No Cloud Scheduler job is required.
   See [scheduler.md](scheduler.md).

---

## 6. Security checklist 🔴 (before the repo is public)

- [ ] `.env` is **not** committed (check `git status`).
- [ ] No API keys or service-account JSON files anywhere in the repo.
- [ ] Firestore **security rules** deny all client writes (only the backend writes).
      See the rule snippet in [schema.md](schema.md) §7.
- [ ] The API checks the user's Firebase Auth token before any approval/write.
      *(This check is a TODO in `backend/app/deps.py`.)*
- [ ] Budget alert is set on the billing account.

---

## Quick status of what's wired vs. what's manual

| Capability | Works out of the box? | Needs manual step |
|---|---|---|
| Core demo (`scripts.demo`) | ✅ yes | — |
| Unit tests | ✅ yes | — |
| API read endpoints (local data) | ✅ yes | — |
| AI agent (`adk run`) | ⚠️ needs key | Step 1 |
| Firestore storage | ✅ code ready | Steps 2–3 (create DB + seed + `DATA_BACKEND=firestore`) |
| Login / roles | ❌ not yet | Step 4 + auth check in `deps.py` |
| Live deployment | ❌ not yet | Step 5 |
