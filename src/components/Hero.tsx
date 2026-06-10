import { profile } from "../data/portfolio";
import "./Hero.css";

export default function Hero() {
  return (
    <section className="hero section" id="hero">
      <div className="hero-bg">
        <div className="hero-gradient" />
        <div className="hero-grid" />
      </div>
      <div className="hero-content">
        <img
          src={profile.heroAvatar}
          alt={profile.avatarAlt}
          className="hero-avatar"
          width={120}
          height={120}
          loading="eager"
          decoding="sync"
          fetchPriority="high"
        />
        <h1 className="hero-name">
          {profile.name}
        </h1>
        <p className="hero-title">
          {profile.title}
        </p>
        <p className="hero-tagline">
          {profile.tagline}
        </p>
        <p className="hero-location">
          {profile.location}
        </p>
        <p className="hero-headline">
          {profile.headline}
        </p>
        <div className="hero-cta">
          <a href={profile.linkedin} target="_blank" rel="noopener noreferrer" className="btn">
            LinkedIn
          </a>
          <a href={profile.github} target="_blank" rel="noopener noreferrer" className="btn btn-ghost">
            GitHub
          </a>
          <a href={profile.cvUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost">
            Download CV
          </a>
          <a href="#contact" className="btn btn-ghost">
            Contact
          </a>
        </div>
      </div>
    </section>
  );
}
