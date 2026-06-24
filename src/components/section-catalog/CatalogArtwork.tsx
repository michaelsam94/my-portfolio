"use client";

import { useState } from "react";

type CatalogArtworkProps = {
  title: string;
  image?: string;
  kind: "apps" | "vscode";
  variant?: "card" | "detail";
};

export default function CatalogArtwork({ title, image, kind, variant = "card" }: CatalogArtworkProps) {
  const [failed, setFailed] = useState(false);
  const isDetail = variant === "detail";

  if (kind === "apps" && image && !failed) {
    return (
      <img
        className={isDetail ? "detail-art-icon" : "catalog-icon"}
        src={image}
        alt={`${title} app icon`}
        loading={isDetail ? "eager" : "lazy"}
        onError={() => setFailed(true)}
      />
    );
  }

  if (kind === "apps") {
    return (
      <span className={isDetail ? "detail-extension-art app-fallback-art" : "catalog-extension-art app-fallback-art"} aria-hidden="true">
        <span>Android App</span>
        <strong>{title.replace(/\s+/g, "").slice(0, isDetail ? 14 : 10)}</strong>
      </span>
    );
  }

  return (
    <span className={isDetail ? "detail-extension-art" : "catalog-extension-art"} aria-hidden="true">
      <span>{isDetail ? "VS Code Extension" : "VS Code"}</span>
      <strong>{title.replace(/\s+/g, "").slice(0, isDetail ? 14 : 10)}</strong>
    </span>
  );
}
