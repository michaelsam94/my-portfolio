import { playStoreApps, profile } from "../data/portfolio";
import "./PlayStore.css";

const featuredApps = playStoreApps.slice(0, 3);
const remainingApps = playStoreApps.slice(3);

export default function PlayStore() {
  return (
    <section className="apps-section" id="apps">
      <div className="apps-shell">
        <div className="apps-heading">
          <p className="apps-kicker">Apps</p>
          <div>
            <h2>Published Android apps</h2>
            <p>
              A live catalog of 24 apps published under MichaelSam94 on Google Play,
              spanning utilities, AI tools, productivity, finance, scanners, and developer apps.
            </p>
          </div>
          <a
            className="apps-store-link"
            href={profile.playStoreDeveloper}
            target="_blank"
            rel="noopener noreferrer"
          >
            View developer page
          </a>
        </div>

        <div className="apps-featured" aria-label="Featured Play Store apps">
          {featuredApps.map((app, index) => (
            <a
              className="apps-featured-card"
              href={app.playStoreUrl}
              key={app.packageId}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className="apps-feature-number">0{index + 1}</span>
              <img src={app.image} alt={`${app.name} app icon`} loading="lazy" />
              <span className="apps-category">{app.category}</span>
              <h3>{app.name}</h3>
              <p>{app.description}</p>
            </a>
          ))}
        </div>

        <div className="apps-grid" aria-label="All Google Play apps">
          {remainingApps.map((app) => (
            <a
              className="apps-card"
              href={app.playStoreUrl}
              key={app.packageId}
              target="_blank"
              rel="noopener noreferrer"
            >
              <img src={app.image} alt={`${app.name} app icon`} loading="lazy" />
              <span>{app.category}</span>
              <h3>{app.name}</h3>
              <p>{app.description}</p>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
