import "./Motion.css";

const motionVideos = [
  {
    title: "Samsung Galaxy Watch 8 | Cinematic Motion Design Reel",
    description:
      "A high-intensity product launch concept for the Samsung Galaxy Watch 8 40mm Graphite. From macro texture reveals to CGI data explosion sequences, the reel explores orbital camera sweeps, heart rate and Energy Score UI motion, chrome material language, and a hard-stop brand lock sequence. Tools: Higgsfield AI, Seedance 2.0, Motion Design.",
    src: "/motion/storyboard-motion-video.mp4",
  },
  {
    title: "Khamrah by Lattafa | Motion Design",
    description:
      "A luxury fragrance film exploring the sensory world of Khamrah, an Oriental Eau de Parfum built on warm vanilla, amber, cinnamon, and golden resins. The visual direction draws from crystal bottle facets, glowing amber liquid, and a deep palette of black, gold, and burnt orange. Tools: Higgsfield AI, Gemini Veo, Claude AI. Style: luxury cinematic, classicMD. Format: 16:9, 15 seconds, 4K.",
    src: "/motion/luxury-performance-motion.mp4",
  },
];

export default function Motion() {
  return (
    <section className="section motion" id="motion" aria-labelledby="motion-heading">
      <div className="motion-header">
        <p className="motion-kicker">Motion Design Portfolio</p>
        <h2 id="motion-heading" className="section-title">
          Motion
        </h2>
        <p className="motion-intro">
          Cinematic product films, kinetic tech reels, and luxury AI video
          concepts crafted for portfolio work.
        </p>
      </div>

      <div className="motion-grid">
        {motionVideos.map((video) => (
          <article key={video.src} className="motion-card glass-card">
            <video
              className="motion-video"
              controls
              muted
              playsInline
              preload="metadata"
            >
              <source src={video.src} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
            <div className="motion-copy">
              <h3>{video.title}</h3>
              <p>{video.description}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
