import { profile } from "../data/portfolio";
import LinkedInProfileBadge from "./LinkedInProfileBadge";
import "./Contact.css";

const SITE_URL = "https://michaelsam94.com/";
const SHARE_TITLE = "Michael Samuel Naeem — Senior Android Developer & Tech Lead";
const SHARE_TEXT =
  "Michael Samuel Naeem — Senior Android Developer & Tech Lead, open to remote jobs and freelance projects.";

function currentUrl() {
  return typeof window !== "undefined" ? window.location.href : SITE_URL;
}

// Instagram and Quora have no web share-intent URL, so route them through the
// native share sheet (mobile) with a copy-link fallback (desktop).
async function shareVia(network: string) {
  const url = currentUrl();
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title: SHARE_TITLE, text: SHARE_TEXT, url });
    } catch {
      /* user dismissed the share sheet */
    }
    return;
  }
  try {
    await navigator.clipboard.writeText(url);
    window.alert(`Link copied — open ${network} and paste it to share.`);
  } catch {
    window.prompt(`Copy this link to share on ${network}:`, url);
  }
}

const links = [
  { href: profile.linkedin, label: "LinkedIn", icon: "in" },
  { href: profile.github, label: "GitHub", icon: "gh" },
  { href: profile.techBlog, label: "Engineering Blog", icon: "ext" },
  { href: profile.playStoreDeveloper, label: "Google Play (developer)", icon: "ext" },
  { href: profile.vscodeMarketplace, label: "VS Code Marketplace", icon: "ext" },
  { href: profile.openVsx, label: "Open VSX", icon: "ext" },
  { href: profile.cvUrl, label: "Download CV", icon: "cv" },
  { href: `mailto:${profile.email}`, label: profile.email, icon: "mail" },
  { href: `tel:${profile.phone.replace(/\s/g, "")}`, label: profile.phone, icon: "phone" },
];

export default function Contact() {
  return (
    <section className="section contact" id="contact">
      <h2 className="section-title">Get in Touch</h2>
      <p className="contact-intro">Open to remote opportunities and interesting projects. Let’s connect.</p>
      <LinkedInProfileBadge />
      <div className="contact-links">
        {links.map(({ href, label, icon }) => (
          <a
            key={label}
            href={href}
            target={href.startsWith("http") ? "_blank" : undefined}
            rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
            className="contact-link glass-card"
          >
            <span className={`contact-icon contact-icon-${icon}`} aria-hidden>
              {icon === "in" && (
                <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              )}
              {icon === "gh" && (
                <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
              )}
              {icon === "mail" && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
              )}
              {icon === "phone" && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              )}
              {icon === "cv" && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              )}
              {icon === "ext" && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20" aria-hidden>
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              )}
            </span>
            <span className="contact-label">{label}</span>
          </a>
        ))}
      </div>
      <div className="share-block" aria-label="Share this page">
        <span className="share-title">Share</span>
        <div className="share-row">
          <a
            className="share-btn"
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(currentUrl())}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Share on LinkedIn"
            title="Share on LinkedIn"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
          </a>
          <a
            className="share-btn"
            href={`https://twitter.com/intent/tweet?url=${encodeURIComponent(currentUrl())}&text=${encodeURIComponent(SHARE_TEXT)}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Share on X (Twitter)"
            title="Share on X"
          >
            <svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor" aria-hidden="true">
              <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z" />
            </svg>
          </a>
          <a
            className="share-btn"
            href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(currentUrl())}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Share on Facebook"
            title="Share on Facebook"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <path d="M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z" />
            </svg>
          </a>
          <button
            type="button"
            className="share-btn"
            onClick={() => shareVia("Quora")}
            aria-label="Share to Quora"
            title="Share to Quora"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <path d="M12.738 18.701c-.831-1.635-1.805-3.287-3.708-3.287a3.616 3.616 0 0 0-1.061.209l-.646-1.291c.786-.674 2.073-1.215 3.731-1.215 2.585 0 3.915 1.244 4.97 2.83.605-1.327.896-3.067.896-5.236 0-5.408-1.688-8.213-5.652-8.213-3.91 0-5.583 2.805-5.583 8.213 0 5.379 1.673 8.143 5.583 8.143.518 0 .992-.045 1.42-.155l-.317-.063zm1.66 1.18c-.93.274-1.928.413-3.08.413C5.589 20.294 2 16.358 2 10.498 2 4.585 5.589.6 11.318.6c5.802 0 9.39 3.965 9.39 9.898 0 3.316-1.127 6.013-3.122 7.746.696.99 1.42 1.65 2.45 1.65.812 0 1.385-.473 1.84-1.18l1.124.892C22.359 21.475 21.156 23.4 18.36 23.4c-2.196 0-3.382-1.273-3.962-2.519z" />
            </svg>
          </button>
          <button
            type="button"
            className="share-btn"
            onClick={() => shareVia("Instagram")}
            aria-label="Share to Instagram"
            title="Share to Instagram"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.012-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
            </svg>
          </button>
        </div>
      </div>
      <p className="contact-footer">Cairo, Egypt · Available for remote roles worldwide</p>
    </section>
  );
}
