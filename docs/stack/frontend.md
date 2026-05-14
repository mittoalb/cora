# Frontend

For implementers picking the browser-side runtime. Frontend code is not yet on disk; current picks are intent, not commitments.

## Picks

| Role | Pick | Why |
| --- | --- | --- |
| Framework | Next.js 15 PWA | Server components, RSC + streaming, mature ecosystem |
| Lint + format | Biome | One tool for JS/TS; faster than ESLint + Prettier |

## To be picked

| Category | Trigger |
| --- | --- |
| Type checker | First TypeScript file lands (likely `tsc`, strict) |
| Component library | First production-bound UI surface |
| State management | First multi-component shared state |
| Testing | First component or page worth a regression test |
| Accessibility tooling | First user-facing surface |
