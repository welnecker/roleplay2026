from __future__ import annotations

import streamlit as st


_PWA_BOOTSTRAP = """
<script>
(() => {
  const parentWindow = window.parent;
  const parentDocument = parentWindow.document;
  const head = parentDocument.head;

  const ensureLink = (rel, href, extra = {}) => {
    let link = head.querySelector(`link[rel="${rel}"]`);
    if (!link) {
      link = parentDocument.createElement("link");
      link.rel = rel;
      head.appendChild(link);
    }
    link.href = href;
    Object.entries(extra).forEach(([key, value]) => link.setAttribute(key, value));
  };

  const ensureMeta = (name, content) => {
    let meta = head.querySelector(`meta[name="${name}"]`);
    if (!meta) {
      meta = parentDocument.createElement("meta");
      meta.name = name;
      head.appendChild(meta);
    }
    meta.content = content;
  };

  ensureLink("manifest", "/app/static/manifest.webmanifest");
  ensureLink("icon", "/app/static/entrecenas-icon.svg", {type: "image/svg+xml"});
  ensureLink("apple-touch-icon", "/app/static/entrecenas-icon.svg");
  ensureMeta("theme-color", "#0C2E2D");
  ensureMeta("mobile-web-app-capable", "yes");
  ensureMeta("apple-mobile-web-app-capable", "yes");
  ensureMeta("apple-mobile-web-app-status-bar-style", "black-translucent");
  ensureMeta("apple-mobile-web-app-title", "EntreCenas");

  if ("serviceWorker" in parentWindow.navigator) {
    parentWindow.navigator.serviceWorker.register(
      "/app/static/service-worker.js"
    ).catch((error) => console.info("EntreCenas PWA:", error));
  }
})();
</script>
"""


def install_pwa_metadata() -> None:
    """Instala metadados públicos da PWA sem cachear conteúdo da sessão."""

    st.html(_PWA_BOOTSTRAP, width="content", unsafe_allow_javascript=True)


__all__ = ["install_pwa_metadata"]
