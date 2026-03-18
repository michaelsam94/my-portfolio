import { motion, useScroll, useTransform } from "framer-motion";
import { useState } from "react";
import { profile } from "../data/portfolio";
import "./Nav.css";

const links = [
  { href: "#about", label: "About" },
  { href: "#experience", label: "Experience" },
  { href: "#projects", label: "Projects" },
  { href: "#skills", label: "Skills" },
  { href: "#contact", label: "Contact" },
];

export default function Nav() {
  const [open, setOpen] = useState(false);
  const { scrollY } = useScroll();
  const navBg = useTransform(scrollY, [0, 120], ["rgba(12,11,15,0)", "rgba(12,11,15,0.92)"]);
  const navBlur = useTransform(scrollY, [0, 120], ["blur(0px)", "blur(14px)"]);

  return (
    <motion.header
      className="nav"
      style={{
        backgroundColor: navBg,
        backdropFilter: navBlur,
      }}
    >
      <div className="nav-inner">
        <a href="#" className="nav-logo">
          {profile.name.split(" ")[0]}
        </a>
        <nav className={`nav-links ${open ? "open" : ""}`}>
          {links.map(({ href, label }) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {label}
            </a>
          ))}
        </nav>
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
    </motion.header>
  );
}
