# Conf T Web

Next.js web app for interactive CLI practice lessons.

## Local development

```bash
cd web
cp .env.local.example .env.local
# Fill in Firebase values (see Environment variables below)
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy on Vercel

1. Import this repository in [Vercel](https://vercel.com/new).
2. Set **Root Directory** to `web` (Project Settings → General).
3. Add the environment variables below (Project Settings → Environment Variables).
4. Deploy. Vercel uses `web/vercel.json` for install/build commands.

`npm run build` runs `prebuild` automatically, which syncs lesson JSON from the repo into `public/`.

### Firebase setup

1. Create a Firebase project (or use an existing one).
2. Enable **Authentication** → Email/Password and Google (if using Google sign-in).
3. Create a **Firestore** database.
4. Under Project settings → Your apps, register a web app and copy the config values into Vercel env vars.
5. Deploy Firestore rules from the repo root:

   ```bash
   firebase deploy --only firestore:rules
   ```

   Rules live in `web/firestore.rules`; `firebase.json` at the repo root points to that file.

### Environment variables

Set these in Vercel (and in `web/.env.local` for local dev). All are required for auth and progress sync.

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Firebase web API key |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Auth domain (e.g. `project-id.firebaseapp.com`) |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Firebase project ID |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | Storage bucket (e.g. `project-id.appspot.com`) |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | Cloud Messaging sender ID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Firebase web app ID |

Copy from Firebase Console → Project settings → Your apps → SDK setup and configuration.

## Lesson deep links

Marketing lesson previews link to `/signup?lesson=<lesson-id>`. After signup, users are sent to `/practice/<lesson-id>` when that query param is present.