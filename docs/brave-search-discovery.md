# Brave Search and Claude Discovery Setup

Brave Search does not currently offer a normal webmaster verification console,
manual sitemap submission, or URL inspection workflow like Google Search Console
or Bing Webmaster Tools.

Use this checklist after deploying `https://michaelsam94.com`.

1. Confirm Brave can crawl the site:
   - `https://michaelsam94.com/robots.txt`
   - `https://michaelsam94.com/sitemap.xml`
   - `https://michaelsam94.com/sitemap.txt`
2. Make sure Googlebot is allowed in `robots.txt`; Brave Search says its crawler
   follows Googlebot crawlability rules.
3. Open the live site in Brave Browser with Web Discovery Project enabled.
4. Search Brave for branded and service-intent queries, then click the canonical
   result when it appears:
   - `Michael Samuel Naeem`
   - `michaelsam94`
   - `Michael Samuel Naeem Android developer`
   - `Michael Samuel Naeem Kotlin React OCPP AI automation`
5. Share canonical URLs directly in channels where real Brave users may visit:
   - `https://michaelsam94.com/`
   - `https://michaelsam94.com/apps/`
   - `https://michaelsam94.com/vscode/`
   - `https://michaelsam94.com/blog/`
6. Keep Bing IndexNow active too. Claude may use Brave, but other AI search
   products and fallbacks can still use Bing or mixed indexes.

Site-side Brave readiness now includes:

- XML sitemap
- Plain-text sitemap
- Open robots access for common crawlers
- Explicit Googlebot allow rule for Brave-compatible crawlability
- Static, crawlable SEO/AEO answer hub and structured data
- LLM-readable context files

Sources:

- Brave Search crawler: https://search.brave.com/help/brave-search-crawler
- Brave Web Discovery Project: https://support.brave.app/hc/en-us/articles/4409406835469-What-is-the-Web-Discovery-Project
- Brave Search: https://brave.com/search/
