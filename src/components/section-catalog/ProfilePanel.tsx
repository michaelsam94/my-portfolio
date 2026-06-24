import Image from "next/image";
import { about, profile } from "@/data/portfolio";

export default function ProfilePanel() {
  return (
    <div className="profile-panel">
      <div className="profile-photo-frame">
        <Image
          src={profile.avatar}
          alt={profile.avatarAlt}
          width={768}
          height={1024}
          sizes="(max-width: 768px) 100vw, 360px"
          priority
          className="profile-photo"
        />
      </div>
      <div className="profile-copy">
        <p>{about.summary}</p>
        <ul>
          {about.highlights.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
