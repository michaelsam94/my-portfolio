# Bing Webmaster Tools Setup

Use this checklist after deploying the latest build to `https://michaelsam94.tech`.

1. Add `https://michaelsam94.tech` in Bing Webmaster Tools.
2. Verify ownership with either DNS verification or Bing's meta tag:
   `<meta name="msvalidate.01" content="YOUR_BING_CODE" />`
3. Submit the sitemap:
   `https://michaelsam94.tech/sitemap.xml`
4. Confirm Bing can fetch the IndexNow key:
   `https://michaelsam94.tech/0eb1eb625c28368318e34f58bec177b0.txt`
5. Run IndexNow submission after deployment:
   `npm run submit:indexnow`
6. In Bing Webmaster Tools, inspect the homepage and request indexing.

The site already includes Bing-friendly crawler access, sitemap discovery, an
IndexNow key file, and an IndexNow bulk URL submitter.
