from __future__ import annotations

import hashlib
from typing import Any, MutableMapping

import streamlit as st

from roleplay.openrouter import OpenRouterError, describe_session_image


ALLOWED_IMAGE_TYPES = ("jpg", "jpeg", "png", "webp")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
PHOTO_ONBOARDING_ENABLED = False
PRIVACY_NOTICE = (
    "As fotos enviadas serão usadas somente durante esta sessão para personalizar "
    "a história. Os arquivos das fotos não serão salvos nem armazenados. A descrição "
    "extraída será guardada como memória desta execução para que a personagem reconheça "
    "você quando retornar. Essa memória termina com a história e não passa para uma nova "
    "execução paga. Todas as etapas são opcionais."
)


def profile_key(user_id: str, package_id: str) -> str:
    return f"immersive_profile:{user_id}:{package_id}"


def identity_is_complete(name: str, story_gender: Any) -> bool:
    return bool(str(name or "").strip() and str(story_gender or "").strip())


def identity_completion_state(*, photos_enabled: bool = PHOTO_ONBOARDING_ENABLED) -> dict[str, object]:
    """Define o próximo estado sem remover a infraestrutura opcional de fotos."""

    if photos_enabled:
        return {"stage": 1, "completed": False}
    return {"stage": 3, "completed": True}


def clear_immersive_profile(
    state: MutableMapping[str, Any], *, user_id: str = "", package_id: str = ""
) -> None:
    prefix = "immersive_profile:"
    exact = profile_key(user_id, package_id) if user_id and package_id else ""
    for key in list(state.keys()):
        key_text = str(key)
        if (exact and key_text == exact) or (not exact and key_text.startswith(prefix)):
            state.pop(key, None)
    if user_id and package_id:
        state.pop(f"immersive_restart:{user_id}:{package_id}", None)


def build_immersive_context(profile: dict[str, Any] | None) -> str:
    if not profile or not profile.get("completed"):
        return ""
    facts: list[str] = []
    name = str(profile.get("preferred_name", "") or "").strip()
    story_gender = str(
        profile.get("story_gender") or profile.get("gender") or ""
    ).strip()
    body_route = str(profile.get("body_route", "") or "").strip()
    appearance = str(profile.get("appearance", "") or "").strip()
    intimate = str(profile.get("intimate", "") or "").strip()
    if name:
        facts.append(f"Nome escolhido pelo usuário: {name}.")
    if story_gender:
        facts.append(f"Tratamento escolhido pelo usuário: {story_gender}.")
    if body_route and body_route != "Prefiro não informar":
        facts.append(f"Anatomia declarada para cenas íntimas: {body_route}.")
    if appearance:
        facts.append(f"Aparência visível informada para esta sessão: {appearance}")
    if intimate:
        facts.append(f"Detalhes íntimos informados para esta sessão: {intimate}")
    if not facts:
        return ""
    return (
        "\n\nCONTEXTO PRIVADO DE IMERSÃO (válido somente nesta sessão):\n- "
        + "\n- ".join(facts)
        + "\nUse apenas quando for natural para a cena. Não diga que analisou uma foto, "
        "não enumere características e não invente detalhes ausentes."
    )


def persistent_profile_payload(profile: dict[str, Any] | None) -> dict[str, str]:
    """Retorna somente texto autorizado para a memória da run; nunca bytes da foto."""

    if not profile or not profile.get("completed"):
        return {}
    return {
        key: str(profile.get(key, "") or "").strip()
        for key in (
            "preferred_name",
            "story_gender",
            "body_route",
            "appearance",
            "intimate",
        )
        if str(profile.get(key, "") or "").strip()
    }


def recover_persistent_profile(messages: list[dict[str, object]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        payload = message.get("immersive_profile")
        if isinstance(payload, dict):
            recovered = {
                **{
                    key: str(payload.get(key, "") or "").strip()
                    for key in (
                        "preferred_name",
                        "story_gender",
                        "body_route",
                        "appearance",
                        "intimate",
                    )
                    if str(payload.get(key, "") or "").strip()
                },
                "completed": True,
                "stage": 3,
            }
            legacy_gender = str(payload.get("gender", "") or "").strip()
            if legacy_gender and not recovered.get("story_gender"):
                recovered["story_gender"] = {
                    "Homem": "Como homem",
                    "Mulher": "Como mulher",
                    "Não binário": "De forma neutra",
                    "Prefiro não informar": "De forma neutra",
                }.get(legacy_gender, legacy_gender)
            return recovered
    return None


def restore_profile_for_run(
    state: MutableMapping[str, Any],
    *,
    user_id: str,
    package_id: str,
    messages: list[dict[str, object]],
) -> None:
    """Recupera a memória textual ou evita onboarding em uma run legada já iniciada."""

    key = profile_key(user_id, package_id)
    current = state.get(key)
    if isinstance(current, dict) and current.get("completed"):
        return
    recovered = recover_persistent_profile(messages)
    if recovered is not None:
        state[key] = recovered
    elif messages:
        state[key] = {"completed": True, "stage": 3}


def photo_acknowledgement(character_name: str, *, intimate: bool = False) -> str:
    name = str(character_name or "A personagem").strip()
    if intimate:
        return (
            f"Humm... gostei muito do que vi. Agora que eu, {name}, conheço você "
            "ainda mais de perto, nossa história vai ficar muito mais íntima e imersiva."
        )
    return (
        f"Humm... gostei do que vi. Agora que eu, {name}, sei quem está do outro "
        "lado, nossa história vai ficar muito mais pessoal e imersiva."
    )


def _image_prompt(kind: str, gender: str) -> str:
    if kind == "appearance":
        return (
            "Descreva em português somente características visuais diretamente observáveis "
            "da pessoa: rosto, cabelo, olhos, pele, barba, corpo e estilo, quando visíveis. "
            "Seja concreto e curto. Não identifique a pessoa e não infira idade, etnia, saúde, "
            "personalidade, orientação sexual ou qualquer atributo não visível."
        )
    return (
        "Esta é uma imagem íntima que um usuário adulto declarou ser dele ou ter autorização "
        "para enviar. Descreva em português, de modo concreto, curto e não médico, apenas a "
        "anatomia adulta diretamente visível, incluindo pelos e características anatômicas "
        "relevantes. Não identifique a pessoa, não estime idade, não diagnostique e não invente. "
        f"Gênero informado, se houver: {gender or 'não informado'}."
    )


def _analyze(uploaded: Any, *, kind: str, api_key: str, model: str, gender: str) -> str:
    image_bytes = uploaded.getvalue()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise OpenRouterError("A imagem deve ter no máximo 8 MB.")
    mime_type = str(getattr(uploaded, "type", "") or "")
    return describe_session_image(
        api_key=api_key,
        model=model,
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=_image_prompt(kind, gender),
        max_tokens=220 if kind == "appearance" else 260,
    )


def _uploaded_digest(uploaded: Any) -> str:
    """Identifica o arquivo na sessão sem conservar seus bytes."""

    return hashlib.sha256(uploaded.getvalue()).hexdigest()


def _analyze_once(
    profile: dict[str, Any],
    uploaded: Any,
    *,
    kind: str,
    api_key: str,
    model: str,
) -> tuple[str, str]:
    """Executa no máximo uma chamada automática para cada arquivo selecionado."""

    attempt_key = f"{kind}_attempt_digest"
    error_key = f"{kind}_error"
    digest = _uploaded_digest(uploaded)
    if profile.get(attempt_key) == digest:
        return "", str(profile.get(error_key, "") or "")

    # Marque antes da chamada: mesmo uma falha não dispara repetição automática.
    profile[attempt_key] = digest
    profile.pop(error_key, None)
    try:
        description = _analyze(
            uploaded,
            kind=kind,
            api_key=api_key,
            model=model,
            gender=str(profile.get("body_route") or profile.get("story_gender") or ""),
        )
    except OpenRouterError as exc:
        error = str(exc)
        profile[error_key] = error
        return "", error
    return description, ""


def render_immersive_onboarding(
    *,
    user_id: str,
    package_id: str,
    title: str,
    character_name: str,
    api_key: str,
    model: str,
) -> bool:
    key = profile_key(user_id, package_id)
    profile = st.session_state.setdefault(key, {"stage": 0, "completed": False})
    if bool(profile.get("completed")):
        return True

    stage = int(profile.get("stage", 0) or 0)
    # Runs que ficaram paradas nas antigas telas de foto também devem seguir direto.
    if not PHOTO_ONBOARDING_ENABLED and stage in {1, 2}:
        profile.update(completed=True, stage=3)
        return True

    st.title(title)
    if PHOTO_ONBOARDING_ENABLED:
        st.info(PRIVACY_NOTICE, icon="🔒")

    if stage == 0:
        st.subheader("Como você quer entrar nesta história?")
        name = st.text_input(
            "Como a personagem deve chamar você?",
            value=str(profile.get("preferred_name", "")),
            placeholder="Nome ou apelido",
        )
        story_gender = st.selectbox(
            "Como você quer ser tratado nesta história?",
            ("Como homem", "Como mulher", "De forma neutra"),
            index=None,
            placeholder="Escolha uma opção",
        )
        body_route = st.selectbox(
            "Qual anatomia deve orientar as cenas íntimas? (opcional)",
            (
                "Prefiro não informar",
                "Corpo masculino",
                "Corpo feminino",
                "Corpo intersexo",
            ),
        )
        can_continue = identity_is_complete(name, story_gender)
        if st.button("Continuar", type="primary", disabled=not can_continue):
            profile.update(
                preferred_name=name.strip(),
                story_gender=str(story_gender),
                body_route=str(body_route),
                **identity_completion_state(),
            )
            st.rerun()
        if not name.strip():
            st.caption("O nome ou apelido é obrigatório.")
        return False

    # A infraestrutura abaixo fica preservada para futura reativação.
    if stage == 1:
        st.subheader("Cole sua foto aqui, para que eu possa saber como você é")
        if profile.get("appearance"):
            st.markdown(f"**{character_name} observa sua foto:**")
            st.write(str(profile["appearance"]))
            st.success(photo_acknowledgement(character_name))
            if st.button("Continuar", type="primary"):
                profile["stage"] = 2
                st.rerun()
            return False
        st.caption("Ao selecionar o arquivo, a análise começará automaticamente.")
        uploaded = st.file_uploader(
            "Foto opcional", type=ALLOWED_IMAGE_TYPES, key=f"appearance_upload:{package_id}"
        )
        if uploaded is not None:
            with st.spinner("Foto recebida. Observando uma única vez..."):
                description, error = _analyze_once(
                    profile, uploaded, kind="appearance", api_key=api_key, model=model
                )
            if description:
                profile["appearance"] = description
                st.rerun()
            if error:
                st.error(error)
                st.caption("A foto não foi processada novamente para evitar consumo duplicado.")
                if st.button("Tentar novamente com esta foto"):
                    profile.pop("appearance_attempt_digest", None)
                    profile.pop("appearance_error", None)
                    st.rerun()
        if st.button("Continuar sem foto"):
            profile["stage"] = 2
            st.rerun()
        return False

    if stage == 2:
        st.subheader("Cole a foto íntima aqui")
        if profile.get("intimate"):
            st.markdown(f"**{character_name} observa sua foto íntima:**")
            st.write(str(profile["intimate"]))
            st.success(photo_acknowledgement(character_name, intimate=True))
            if st.button("Iniciar história", type="primary"):
                profile.update(completed=True, stage=3)
                st.rerun()
            return False
        st.warning("Envie somente uma imagem sua, sendo maior de 18 anos, ou uma imagem que você tenha autorização expressa para usar.")
        adult = st.checkbox(
            "Confirmo que tenho 18 anos ou mais.",
            key=f"intimate_adult:{package_id}",
        )
        authorized = st.checkbox(
            "Confirmo que a imagem é minha ou tenho autorização expressa.",
            key=f"intimate_authorized:{package_id}",
        )
        uploaded = st.file_uploader(
            "Foto íntima opcional", type=ALLOWED_IMAGE_TYPES, key=f"intimate_upload:{package_id}"
        )
        if uploaded is not None and not (adult and authorized):
            st.info("Foto recebida. Marque as duas confirmações para iniciar a análise.")
        if uploaded is not None and adult and authorized:
            with st.spinner("Foto recebida. Observando uma única vez..."):
                description, error = _analyze_once(
                    profile, uploaded, kind="intimate", api_key=api_key, model=model
                )
            if description:
                profile["intimate"] = description
                st.rerun()
            if error:
                st.error(error)
                st.caption("A foto não foi processada novamente para evitar consumo duplicado.")
                if st.button("Tentar novamente com esta foto"):
                    profile.pop("intimate_attempt_digest", None)
                    profile.pop("intimate_error", None)
                    st.rerun()
        if st.button("Continuar sem foto íntima"):
            profile.update(completed=True, stage=3)
            st.rerun()
        return False

    profile["completed"] = True
    return True
