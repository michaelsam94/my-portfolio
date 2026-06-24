"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ProjectData } from "@/data/portfolio";
import { easeOut } from "@/lib/motion";
import { cn } from "@/lib/utils";
import ProjectCardMedia from "./ProjectCardMedia";

export default function ProjectCard({ project }: { project: ProjectData }) {
  const reducedMotion = useReducedMotion();
  const primaryLink = project.links[0]?.href;

  const openPrimary = () => {
    if (primaryLink) {
      window.open(primaryLink, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <motion.article
      whileHover={reducedMotion ? {} : { y: -4, boxShadow: "var(--shadow-card-hover)" }}
      transition={easeOut}
      className={cn("project-card", project.highlight && "highlight")}
      tabIndex={0}
      aria-label={`Project: ${project.title}`}
      onKeyDown={(event) => {
        if ((event.key === "Enter" || event.key === " ") && primaryLink) {
          event.preventDefault();
          openPrimary();
        }
      }}
    >
      <ProjectCardMedia media={project.media} title={project.title} />
      <div className="project-body">
        <p className="project-meta">
          {project.year} / {project.company}
        </p>
        <h3 className="project-title">{project.title}</h3>
        <p className="project-desc">{project.description}</p>
        <ul className="tag-list" aria-label="Technologies used">
          {project.tags.map((tag) => (
            <li key={tag} className="tag">
              {tag}
            </li>
          ))}
        </ul>
        <div className="card-links" aria-label={`${project.title} links`}>
          {project.links.map((link) => (
            <a key={link.href} className="text-link" href={link.href} target="_blank" rel="noopener noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </motion.article>
  );
}
