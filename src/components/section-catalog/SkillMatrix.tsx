import { skillGroups } from "@/data/portfolio";

export default function SkillMatrix() {
  return (
    <div className="skill-grid">
      {skillGroups.map((group) => (
        <article key={group.title} className="plain-card">
          <h3>{group.title}</h3>
          <ul className="tag-list" aria-label={`${group.title} skills`}>
            {group.items.map((skill) => (
              <li key={skill} className="tag">
                {skill}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
