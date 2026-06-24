# Tactile Brutalism Next Portfolio Implementation Plan

**For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans implement plan task-by-task. Steps use checkbox (`- [ ]`) syntax tracking.

**Goal:** Migrate the portfolio from Vite React to a Next.js App Router static export with a tactile brutalist single-page UI.

**Architecture:** Keep the existing content source, but reshape it into typed static data consumed by App Router server components. Client behavior is isolated to theme toggling, clipboard copy, and motion-enabled project cards. Legacy Vite entry files are excluded from TypeScript and ESLint so the migration can land without noisy unrelated rewrites.

**Tech Stack:** Next.js App Router, TypeScript strict mode, Tailwind-compatible tokens, Framer Motion, next-themes, lucide-react, clsx, tailwind-merge.

---

### Task 1: Establish Static Export Skeleton

**Files:**
- Create: `next.config.mjs`
- Create: `next-env.d.ts`
- Modify: `package.json`
- Modify: `tsconfig.json`
- Modify: `eslint.config.js`
- Create: `postcss.config.mjs`
- Create: `tailwind.config.ts`

- [ ] Add Next.js scripts and dependencies.
- [ ] Enable `output: "export"` and `images.unoptimized`.
- [ ] Configure strict TypeScript with `@/*` imports.
- [ ] Exclude legacy direct `src/components/*.tsx`, `src/App.tsx`, and `src/main.tsx`.

### Task 2: Add Typed Content and SEO Helpers

**Files:**
- Replace: `src/data/portfolio.ts`
- Create: `src/lib/utils.ts`
- Create: `src/lib/metadata.ts`
- Create: `src/lib/motion.ts`

- [ ] Define hero, projects, experience, contact links, FAQ, and compatibility exports for existing static generators.
- [ ] Add schema.org Person and WebSite graph helpers.
- [ ] Add `cn()` and motion transition constants.

### Task 3: Build App Router UI

**Files:**
- Create: `src/app/layout.tsx`
- Create: `src/app/page.tsx`
- Create: `src/app/globals.css`
- Create: `src/components/SkipLink.tsx`
- Create: `src/components/SectionWrapper.tsx`
- Create: `src/components/ThemeProvider.tsx`
- Create: `src/components/ThemeToggle.tsx`
- Create: `src/components/hero/HeroGrid.tsx`
- Create: `src/components/hero/StatusTag.tsx`
- Create: `src/components/hero/CopyEmail.tsx`
- Create: `src/hooks/useCopyToClipboard.ts`
- Create: `src/components/projects/ProjectGrid.tsx`
- Create: `src/components/projects/ProjectCard.tsx`
- Create: `src/components/projects/ProjectCardMedia.tsx`
- Create: `src/components/work/Timeline.tsx`
- Create: `src/components/contact/ContactLinks.tsx`

- [ ] Render the approved single-page structure.
- [ ] Use tactile tokens, 1px grid gutters, offset shadows, and reduced-motion-safe interactions.
- [ ] Keep contact to copy email plus sparse external links.

### Task 4: Retarget Static Generators and Verify

**Files:**
- Modify: `scripts/build-blog.mjs`
- Modify: `scripts/enhance-product-seo.mjs`
- Modify: `scripts/verify-static-site.mjs`

- [ ] Change generator output from `dist` to `out`.
- [ ] Run the static-site verifier before and after implementation.
- [ ] Run `npm run type-check`, `npm run lint`, and `npm run build`.
