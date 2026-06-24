import { motionVideos } from "@/data/portfolio";

export default function MotionGrid() {
  return (
    <>
      <p className="motion-note">
        Optional side creative work, kept separate from the core engineering case. The main hiring signal on this
        portfolio is senior Android engineering, mobile architecture, production systems, and developer tools; these
        reels are only a glimpse of product storytelling instincts.
      </p>
      <div className="motion-grid">
        {motionVideos.map((video) => (
          <article key={video.src} className="plain-card motion-card">
            <video controls muted playsInline preload="metadata">
              <source src={video.src} type="video/mp4" />
            </video>
            <span className="project-meta">Optional side work / product storytelling study</span>
            <div className="plain-card-title">{video.title}</div>
            <p>{video.description}</p>
          </article>
        ))}
      </div>
    </>
  );
}
