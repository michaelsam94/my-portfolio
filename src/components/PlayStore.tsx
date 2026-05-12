import { playStoreApps, profile } from "../data/portfolio";
import "./PlayStore.css";

export default function PlayStore() {
  return (
    <section className="section play-store" id="play-store">
      <h2 className="section-title">Google Play & App Store</h2>
      <p className="play-store-intro">
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
      </p>
      <div className="play-store-grid">
        {playStoreApps.map((app) => (
          <article key={app.packageId} className="play-store-card glass-card">
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
          </article>
        ))}
      </div>
    </section>
  );
}
