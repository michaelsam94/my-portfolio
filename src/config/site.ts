/**
 * Canonical public URL for this site. Used in code for absolute links.
 * Keep in sync with `index.html` (canonical, Open Graph, JSON-LD) and `public/sitemap.xml` (including `<lastmod>` when you ship meaningful SEO/content updates).
 * In Netlify, set this domain as primary and add a 301 redirect from any `*.netlify.app` hostname so search engines consolidate on one URL.
 */
export const SITE_ORIGIN = "https://michaelsam94.tech" as const;

export function absoluteUrl(path = "/"): string {
  if (path === "/" || path === "") return SITE_ORIGIN;
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_ORIGIN}${p}`;
}
