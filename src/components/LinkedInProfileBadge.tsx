import { useEffect } from "react";
import { profile } from "../data/portfolio";

const SCRIPT_SRC = "https://platform.linkedin.com/badges/js/profile.js";

function linkedinVanity(url: string): string {
  const m = url.match(/linkedin\.com\/in\/([^/?#]+)/i);
  return m?.[1] ?? "michaelsam00";
}

export default function LinkedInProfileBadge() {
  const vanity = linkedinVanity(profile.linkedin);
  const badgeHref = `https://eg.linkedin.com/in/${vanity}?trk=profile-badge`;
  const badgeLabel = profile.name.split(/\s+/).slice(0, 2).join(" ");

  useEffect(() => {
    if (document.querySelector(`script[src="${SCRIPT_SRC}"]`)) return;
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.type = "text/javascript";
    document.body.appendChild(s);
  }, []);

  return (
    <div className="contact-linkedin-badge-wrap">
      <div
        className="badge-base LI-profile-badge"
        data-locale="en_US"
        data-size="large"
        data-theme="dark"
        data-type="HORIZONTAL"
        data-vanity={vanity}
        data-version="v1"
      >
        <a
          className="badge-base__link LI-simple-link"
          href={badgeHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          {badgeLabel}
        </a>
      </div>
    </div>
  );
}
