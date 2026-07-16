import CopyEmail from "@/components/hero/CopyEmail";
import { site } from "@/data/portfolio";

type ContactLinksProps = {
  email: string;
  links: readonly { label: string; href: string }[];
};

export default function ContactLinks({ email, links }: ContactLinksProps) {
  const shareUrl = encodeURIComponent(site.origin);
  const shareText = encodeURIComponent("Michael Samuel Naeem - Senior Android Engineer");

  return (
    <div className="contact-panel">
      <div>
        <p className="contact-copy">
          Open senior Android, staff mobile, mobile architect, technical lead roles with teams that care about systems,
          shipping, and details users feel.
        </p>
        <div className="contact-actions">
          <CopyEmail email={email} />
          <a className="text-link" href={`mailto:${email}`}>
            Open mail client
          </a>
        </div>
      </div>
      <nav className="hero-links" aria-label="Contact links">
        {links.map((link) => (
          <a key={link.href} className="text-link" href={link.href} target="_blank" rel="noopener noreferrer">
            {link.label}
          </a>
        ))}
      </nav>
      <nav className="hero-links contact-share" aria-label="Share this portfolio">
        <a
          className="text-link"
          href={`https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Share on LinkedIn
        </a>
        <a
          className="text-link"
          href={`https://twitter.com/intent/tweet?url=${shareUrl}&text=${shareText}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Share on X
        </a>
      </nav>
    </div>
  );
}
