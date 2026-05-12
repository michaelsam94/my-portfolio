/**
 * Canonical public URL for this site. Used in code for absolute links.
 * Keep in sync with `index.html` (canonical, Open Graph, JSON-LD) and `public/sitemap.xml` (including `<lastmod>` when you ship meaningful SEO/content updates).
 * If you add a custom domain on Netlify, update this and those files together.
 */
export const SITE_ORIGIN = "https://michaelsam00.netlify.app" as const;

export function absoluteUrl(path = "/"): string {
  if (path === "/" || path === "") return SITE_ORIGIN;
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_ORIGIN}${p}`;
}
