import CopyEmail from "@/components/hero/CopyEmail";

type ContactLinksProps = {
  email: string;
  links: readonly { label: string; href: string }[];
};

export default function ContactLinks({ email, links }: ContactLinksProps) {
  return (
    <div className="contact-panel">
      <div>
        <p className="contact-copy">
          Open to senior Android, staff mobile, mobile architect, and technical lead roles with teams that care about
          systems, shipping, and the details users feel.
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
    </div>
  );
}
