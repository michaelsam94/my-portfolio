import { BookOpen, Github, Linkedin, Store } from "lucide-react";
import type { HeroData } from "@/data/portfolio";
import CopyEmail from "./CopyEmail";
import StatusTag from "./StatusTag";

const icons = {
  book: BookOpen,
  github: Github,
  linkedin: Linkedin,
  store: Store,
};

export default function HeroGrid({ data }: { data: HeroData }) {
  return (
    <section className="hero-grid" aria-labelledby="hero-heading">
      <div className="hero-copy">
        <p className="hero-kicker">
          {data.location} / {data.title}
        </p>
        <h1 id="hero-heading" className="hero-title">
          {data.name}
        </h1>
        <p className="hero-headline">{data.headline}</p>
        <div className="hero-actions">
          <CopyEmail email={data.email} />
          <a className="text-link" href="#projects">
            Read field notes
          </a>
        </div>
      </div>
      <aside className="hero-rail" aria-label="Availability and links">
        <StatusTag status={data.status} available={data.statusAvailable} />
        <nav className="hero-links" aria-label="External profiles">
          {data.links.map((link) => {
            const Icon = icons[link.icon];
            return (
              <a key={link.href} className="text-link" href={link.href} target="_blank" rel="noopener noreferrer">
                <Icon size={16} aria-hidden="true" />
                {link.label}
              </a>
            );
          })}
        </nav>
      </aside>
    </section>
  );
}
