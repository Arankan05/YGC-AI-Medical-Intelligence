# MediGuardian AI — Frontend

Next.js (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui implementation of
the **MediGuardian AI** Figma file (`MediGuardian AI — Design`).

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

## Screens

Every Figma frame has a route. The Figma node id is noted in a comment at the
top of each page component.

| Figma frame | Route |
| --- | --- |
| 01 · Sign In | `/sign-in` |
| 02 · Create Account | `/sign-up` |
| 03 · First Run — Empty State | `/welcome` |
| 04 · Documents | `/documents` |
| 05 · Upload & OCR Pipeline | `/documents/upload` |
| 06 · Patient Timeline | `/timeline` |
| 07 · Dashboard | `/dashboard` |
| 08 · Medications & Cross-Check | `/medications` |
| 09 · Lab Results & Trends | `/lab-results` |
| 10 · AI Findings | `/findings` |
| 11 · Finding Detail | `/findings/[findingId]` |
| 12 · Ask AI | `/ask-ai` |
| 13 · Ask AI — No-Diagnosis Safety | `/ask-ai/safety` |
| 14 · Provider Search Setup | `/providers` |
| 15 · Provider Results | `/providers/results` |
| 16 · No Providers Found | `/providers/results?state=empty` |
| 17 · Provider Service Unavailable | `/providers/results?state=unavailable` |
| 18 · Profile & Security | `/profile` |

## Structure

```
src/
  app/
    (auth)/        sign-in, sign-up — shares the Figma brand panel
    (app)/         every signed-in screen, wrapped in <AppShell>
  components/      design-system pieces (RiskBadge, StatusPill, MetricCard, …)
    ui/            shadcn/ui primitives
  lib/
    api.ts         backend integration points  ← wire the API here
    data.ts        screen content transcribed from Figma
    types.ts       frontend domain types
    navigation.ts  sidebar structure
```

## Design tokens

`src/app/globals.css` mirrors the Figma variables one-for-one
(`brand/700` → `--brand-700` → `bg-brand-700`), plus the three text styles that
need a custom utility: `.type-overline`, `.type-display`, `.type-metric`.
Custom brand SVGs exported from Figma live in `public/brand/`; every other icon
is the matching `lucide-react` glyph at the designed size and stroke width.

## Connecting the backend

Nothing in this app calls a server. `src/lib/api.ts` declares one typed
operation per server-dependent action (`signIn`, `uploadDocument`, `askAi`,
`searchProviders`, `deleteAccount`, …). Until an implementation is registered,
each rejects with `ApiNotConfiguredError`, which the screens surface as an
inline error rather than failing silently.

```ts
import { configureApi } from "@/lib/api";

configureApi({
  async listDocuments() {
    /* real call */
  },
});
```

Screens currently render from `src/lib/data.ts`, which holds the exact content
shown in the Figma frames. Swap those reads for `api()` calls as endpoints land
— the types are identical, so no component changes are needed.

The provider map (`src/components/provider-map.tsx`) renders the panel, radius
ring, markers and OpenStreetMap attribution; the Leaflet tile layer mounts into
the container marked `data-map-surface`.
