# Tactile Brutalism Next Portfolio Design

## Goal
Migrate the current Vite portfolio to a Next.js App Router static export that presents Michael Samuel Naeem as a senior Android/mobile architect through a restrained "Tactile Brutalism / Resonant Stark" interface.

## Scope
The first shipped version is a single static home page with hero, selected projects, experience, and contact sections. It preserves existing portfolio content, SEO assets, blog/product static generators, and Cloudflare static hosting expectations.

## Architecture
The app uses Next.js App Router under `src/app`, statically exported to `out` through `next.config.mjs`. Presentational pieces live in `src/components/*`, browser orchestration in `src/hooks/*`, pure helpers in `src/lib/*`, and typed content in `src/data/*`.

## Visual System
The design is pure typography, hard borders, 1px gutters, offset shadows, and small monospaced section labels. There are no hero images, gradients, blobs, nested cards, contact forms, or decorative noise. The signature element is the "field report" project grid: content-dense cards with terminal/image/video media slots and crisp tactile hover/focus states.

## Accessibility
The skip link is the first focusable element. Interactive targets meet 44px minimum touch sizing. Project cards are keyboard-focusable, contact copy announces status through an ARIA live region, theme toggle waits for mount to avoid hydration mismatch, and timeline content remains semantic ordered-list HTML.

## Performance
Hero text is server-rendered HTML. Framer Motion is used only in client components for hover/copy feedback. Project media uses fixed aspect-ratio containers, and the static export avoids runtime server work. Verification uses typecheck, lint, `next build`, and `scripts/verify-static-site.mjs`.
