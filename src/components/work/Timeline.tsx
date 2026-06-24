import type { ExperienceData } from "@/data/portfolio";
import { cn } from "@/lib/utils";

export default function Timeline({ experience }: { experience: ExperienceData[] }) {
  return (
    <ol className="timeline" aria-label="Work experience timeline">
      {experience.map((item) => (
        <li key={`${item.company}-${item.period.start}`} className="timeline-item">
          <span aria-hidden="true" className={cn("timeline-dot", item.isCurrent && "current")} />
          <article className="timeline-card">
            <p className="timeline-meta">
              {item.period.start} - {item.period.end}
            </p>
<h3>{item.role} at {item.company}</h3>
            <p className="timeline-meta">{item.company}</p>
            <ul aria-label={`${item.company} responsibilities`}>
              {item.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </article>
        </li>
      ))}
    </ol>
  );
}
