import { motionVideos } from "@/data/portfolio";

export default function MotionGrid() {
  return (
    <div className="motion-grid">
      {motionVideos.map((video) => (
        <article key={video.src} className="plain-card motion-card">
          <video controls muted playsInline preload="metadata">
            <source src={video.src} type="video/mp4" />
          </video>
          <h3>{video.title}</h3>
          <p>{video.description}</p>
        </article>
      ))}
    </div>
  );
}
