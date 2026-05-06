import { motion } from "framer-motion";
import { profile } from "../data/portfolio";
import "./Hero.css";

export default function Hero() {
  return (
    <section className="hero section" id="hero">
      <div className="hero-bg">
        <div className="hero-gradient" />
        <div className="hero-grid" />
      </div>
      <motion.div
        className="hero-content"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <motion.img
          src={profile.avatar}
          alt={profile.avatarAlt}
          className="hero-avatar"
          width={120}
          height={120}
          fetchPriority="high"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        />
        <motion.h1
          className="hero-name"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
        >
          {profile.name}
        </motion.h1>
        <motion.p
          className="hero-title"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          {profile.title}
        </motion.p>
        <motion.p
          className="hero-tagline"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
        >
          {profile.tagline}
        </motion.p>
        <motion.p
          className="hero-location"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
        >
          {profile.location}
        </motion.p>
        <motion.p
          className="hero-headline"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.65, duration: 0.5 }}
        >
          {profile.headline}
        </motion.p>
        <motion.div
          className="hero-cta"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.5 }}
        >
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
        </motion.div>
      </motion.div>
    </section>
  );
}
