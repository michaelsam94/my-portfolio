import Image from "next/image";
import type { ProjectData } from "@/data/portfolio";

export default function ProjectCardMedia({ media, title }: { media: ProjectData["media"]; title: string }) {
  if (media.type === "image") {
    return (
      <div className="project-media">
        <Image src={media.src} alt={media.alt} fill sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw" />
      </div>
    );
  }

  if (media.type === "video") {
    return (
      <div className="project-media">
        <video autoPlay loop muted playsInline poster={media.poster} aria-label={media.alt ?? `${title} motion preview`}>
          <source src={media.src} />
        </video>
      </div>
    );
  }

  return (
    <div className="project-media" aria-label={`${title} terminal summary`}>
      <pre className="terminal">
        {media.terminalLines.map((line) => (
          <span key={line} className="terminal-line">
            {line}
          </span>
        ))}
      </pre>
    </div>
  );
}
