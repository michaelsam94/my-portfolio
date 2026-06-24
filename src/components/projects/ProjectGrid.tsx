import type { ProjectData } from "@/data/portfolio";
import ProjectCard from "./ProjectCard";

export default function ProjectGrid({ projects }: { projects: ProjectData[] }) {
  return (
    <div className="project-grid" aria-labelledby="projects-heading">
      {projects.slice(0, 12).map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  );
}
