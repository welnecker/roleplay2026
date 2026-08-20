from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_streamlit_habilita_arquivos_estaticos_da_pwa() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "enableStaticServing = true" in config


def test_manifesto_pwa_tem_identidade_e_escopo_publicos() -> None:
    manifest = (ROOT / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
    assert '"name": "EntreCenas"' in manifest
    assert '"display": "standalone"' in manifest
    assert '"scope": "/"' in manifest
    assert "entrecenas-icon.svg" in manifest


def test_service_worker_nao_cacheia_dados_dinamicos() -> None:
    worker = (ROOT / "static" / "service-worker.js").read_text(encoding="utf-8")
    assert "PUBLIC_ASSETS" in worker
    assert "manifest.webmanifest" in worker
    assert "entrecenas-icon.svg" in worker
    assert "caches.match(request)" in worker
    assert "fetch(request)" in worker
    assert "stcore" not in worker.casefold()
    assert "payment" not in worker.casefold()


def test_telas_principais_instalam_metadados_da_pwa() -> None:
    paths = (
        ROOT / "app.py",
        ROOT / "pages" / "1_Pagamento_Pix.py",
        ROOT / "pages" / "3_Auxiliar_de_Roteiros.py",
        ROOT / "services" / "novel_player_runtime.py",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "install_pwa_metadata()" in source, path


def test_bootstrap_pwa_usa_api_atual_do_streamlit() -> None:
    source = (ROOT / "services" / "pwa.py").read_text(encoding="utf-8")
    assert "st.html(" in source
    assert "unsafe_allow_javascript=True" in source
    assert "components.html(" not in source
