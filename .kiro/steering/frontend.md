# TalentLens Frontend — Coding Standards & Patterns

## Stack

- React 18 + Vite 5 + TypeScript (strict mode)
- Tailwind CSS for styling
- Zustand for state management (auth, session, ranking stores)
- Axios for HTTP (configured in `src/api/client.ts`)
- AWS Amplify v6 for Cognito auth (`aws-amplify`)
- React Router v6 for routing
- Vitest for unit tests

## API Client

All API calls go through `src/api/client.ts` which:
1. Creates an Axios instance with `baseURL = VITE_API_BASE_URL`
2. Adds a request interceptor that calls `fetchAuthSession()` and attaches `Authorization: Bearer <idToken>`
3. Adds a response interceptor that extracts `detail` from error responses

**Never use `window.open()` or `<a href>` for authenticated endpoints** — these bypass the Axios interceptor and will get `{"detail":"Missing Authorization header"}`. Always use `apiClient.get()` with `responseType: "blob"` for file downloads.

```typescript
// Correct pattern for authenticated file download
export async function downloadExportCsv(sessionId: string, jobId: string): Promise<void> {
  const response = await apiClient.get(`/sessions/${sessionId}/export`, {
    params: { job_id: jobId },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `filename.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
```

## Environment Variables

All env vars are injected at build time via `.env.production`:

```
VITE_API_BASE_URL=https://izjdvv4mshj2b334e67szsidga0ljndx.lambda-url.us-east-1.on.aws/
VITE_COGNITO_USER_POOL_ID=us-east-1_Sq0dthN4S
VITE_COGNITO_CLIENT_ID=gap4a5ko95q1a1vcu48efak51
```

## Cognito Auth Config

Configured in `src/api/auth-config.ts` using Amplify v6:

```typescript
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
      signUpVerificationMethod: "code",
      loginWith: { email: true },
    },
  },
});
```

## TypeScript Types

All types in `src/types/` mirror the backend Pydantic models exactly. Always keep them in sync when modifying backend models.

## Running & Building

```powershell
# Development
cd frontend
npm install
npm run dev   # http://localhost:5173

# Production build
npm run build   # outputs to dist/

# Tests
npx vitest run
```

## Deploying Frontend

```powershell
cd frontend
npm run build
aws s3 sync dist/ s3://talentlens-frontend-022784798053 --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id E1XZFFKONJ3KTG --paths "/*"
```

## Pages

| Page | Route | Purpose |
|---|---|---|
| Login | `/login` | Cognito sign in / sign up |
| Dashboard | `/dashboard` | List all sessions, create new session |
| Session | `/sessions/:id` | JD analysis wizard + resume upload |
| Shortlist | `/sessions/:id/shortlist` | Ranked candidates + weight adjustment + CSV export |
