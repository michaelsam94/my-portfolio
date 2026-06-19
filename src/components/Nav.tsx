import { useState } from "react";
import { profile } from "../data/portfolio";
import ThemeToggle from "./ThemeToggle";
import "./Nav.css";

const links = [
  { href: "#about", label: "About" },
  { href: "#experience", label: "Experience" },
  { href: "#projects", label: "Projects" },
  { href: "/blog/", label: "Blog" },
  { href: "#apps", label: "Apps" },
  { href: "#open-source", label: "Open Source" },
  { href: "#skills", label: "Skills" },
  { href: "#contact", label: "Contact" },
];

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="nav">
      <div className="nav-inner">
        <a href="#hero" className="nav-logo">
          {profile.name.split(" ")[0]}
        </a>
        <nav className={`nav-links ${open ? "open" : ""}`}>
          {links.map(({ href, label }) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {label}
            </a>
          ))}
        </nav>
        <div className="nav-actions">
          <ThemeToggle />
          <button
            type="button"
            className="nav-toggle"
            aria-label="Toggle menu"
            onClick={() => setOpen(!open)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>
    </header>
  );
}
