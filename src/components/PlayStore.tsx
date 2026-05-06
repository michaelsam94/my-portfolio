import { motion } from "framer-motion";
import { playStoreApps, profile } from "../data/portfolio";
import "./PlayStore.css";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
};

const card = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export default function PlayStore() {
  return (
    <section className="section play-store" id="play-store">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Google Play & App Store
      </motion.h2>
      <motion.p
        className="play-store-intro"
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.45 }}
      >
        Production apps I’ve shipped or contributed to—see also my{" "}
        <a href={profile.playStoreDeveloper} target="_blank" rel="noopener noreferrer">
          Google Play developer page (MichaelSam94)
        </a>
        . Summaries from{" "}
        <a href="https://play.google.com/" target="_blank" rel="noopener noreferrer">
          Google Play
        </a>{" "}
        and, where linked, the{" "}
        <a href="https://www.apple.com/app-store/" target="_blank" rel="noopener noreferrer">
          App Store
        </a>
        .
      </motion.p>
      <motion.div
        className="play-store-grid"
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        {playStoreApps.map((app) => (
          <motion.article
            key={app.packageId}
            className="play-store-card glass-card"
            variants={card}
            whileHover={{ y: -4 }}
          >
            <div className="play-store-card-head">
              <h3 className="play-store-name">{app.name}</h3>
              <div className="play-store-badges">
                <span className="play-store-badge play-store-badge--play">Play</span>
                {app.appStoreUrl ? (
                  <span className="play-store-badge play-store-badge--ios">App Store</span>
                ) : null}
              </div>
            </div>
            <p className="play-store-developer">{app.developer}</p>
            <dl className="play-store-meta">
              <div>
                <dt>Play category</dt>
                <dd>{app.category}</dd>
              </div>
              <div>
                <dt>Installs</dt>
                <dd>{app.installs}</dd>
              </div>
              {"rating" in app && app.rating ? (
                <div>
                  <dt>Play rating</dt>
                  <dd>
                    {app.rating}★
                    {app.reviewCount ? ` · ${app.reviewCount} reviews` : ""}
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>Content</dt>
                <dd>{app.contentRating}</dd>
              </div>
              {app.appStoreUrl && app.iosCategory ? (
                <div>
                  <dt>App Store</dt>
                  <dd>{app.iosCategory}</dd>
                </div>
              ) : null}
              {app.appStoreUrl && app.iosRating ? (
                <div>
                  <dt>iOS rating</dt>
                  <dd>
                    {app.iosRating}★
                    {app.iosRatingsCount ? ` · ${app.iosRatingsCount}` : ""}
                  </dd>
                </div>
              ) : null}
            </dl>
            <p className="play-store-about">{app.about}</p>
            <div className="play-store-tags">
              {app.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
            <div className="play-store-ctas">
              <a
                href={app.storeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="play-store-cta"
              >
                Google Play →
              </a>
              {app.appStoreUrl ? (
                <a
                  href={app.appStoreUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="play-store-cta play-store-cta--ios"
                >
                  App Store →
                </a>
              ) : null}
            </div>
          </motion.article>
        ))}
      </motion.div>
    </section>
  );
}
