from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import re
import yaml

from services.organic_interaction import detect_organic_signal, render_facts

Engagement = Literal["engaged", "minimal", "dismissive", "mocking", "hostile", "nonsense"]


@dataclass(slots=True)
class PilotState:
    node_id: str = ""
    interest: int = 5
    desire: int = 3
    trust: int = 2
    patience: int = 4
    recent_engagement: list[str] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    pending_next_beat_id: str = ""
    interstitial_turns: int = 0
    finished: bool = False
    run_status: str = "active"
    ending_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> "PilotState":
        if not isinstance(raw, dict):
            return cls()
        return cls(
            node_id=str(raw.get("node_id", "") or ""),
            interest=int(raw.get("interest", 5) or 0),
            desire=int(raw.get("desire", 3) or 0),
            trust=int(raw.get("trust", 2) or 0),
            patience=int(raw.get("patience", 4) or 0),
            recent_engagement=[str(item) for item in raw.get("recent_engagement", [])][-4:],
            facts={str(key): str(value) for key, value in dict(raw.get("facts") or {}).items()},
            pending_next_beat_id=str(raw.get("pending_next_beat_id", "") or ""),
            interstitial_turns=int(raw.get("interstitial_turns", 0) or 0),
            finished=bool(raw.get("finished", False)),
            run_status=str(raw.get("run_status", "active") or "active"),
            ending_code=str(raw.get("ending_code", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class PilotTurn:
    engagement: Engagement
    target_id: str
    visible_fallback: str
    system_prompt: str
    state: PilotState
    finished: bool = False
    run_status: str = "active"
    ending_code: str = ""


class PilotScript:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.scene = raw.get("scene") or {}
        self.beats = {
            str(item["beat_id"]): item
            for item in self.scene.get("beats", [])
            if isinstance(item, dict) and item.get("beat_id")
        }
        self.endings = {
            str(item["ending_id"]): item
            for item in self.scene.get("endings", [])
            if isinstance(item, dict) and item.get("ending_id")
        }
        if not self.beats:
            raise ValueError("O roteiro editorial não contém beats ativos.")
        configured_first = str(self.scene.get("first_beat_id", "") or "").strip()
        self.first_beat_id = configured_first if configured_first in self.beats else next(iter(self.beats))
        self.engagement_policy = raw.get("engagement_policy") or {}

    @classmethod
    def load(cls, path: Path) -> "PilotScript":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("dialogue_pilot.yaml inválido.")
        return cls(raw)


_MINIMAL = {
    "sim", "não", "nao", "aham", "uhum", "certo", "ok", "tá", "ta", "sei",
    "vou", "beleza", "entendi", "claro",
}
_DISMISSIVE = {
    "vai", "continua", "segue", "anda", "anda logo", "faz logo", "próxima",
    "proxima", "vai logo", "segue o roteiro", "continue",
}
_HOSTILE_MARKERS = {
    "idiota", "burra", "imbecil", "vagabunda", "vadia", "cala a boca",
    "vai se foder", "te odeio", "ameaço", "ameaco",
}
_MOCKING_MARKERS = {
    "sou o batman", "sou superman", "mulher maravilha", "segue o roteiro",
    "que roteiro", "npc", "robô", "robo", "personagem", "chatbot",
    "faz sua fala", "diz sua fala",
}

_FORBIDDEN_NARRATION = (
    r"\bMary\b",
    r"\bela\s+",
    r"\b(?:eu\s+)?(?:arregalo|sorrio|rio|dou um passo|caminho|seguro|ajeito|observo|olho|recuo|respiro|inclino|aproximo|afasto|encosto|mantenho|viro|cruzo|descruzo|levanto|abaixo|mordo|lambo|chupo|beijo)\b",
    r"\b(?:meus?|minhas?)\s+(?:olhos|mãos|lábios|pernas|braços|dedos)\b",
    r"\b(?:contato visual|carrinho com as duas mãos|passo para trás|sorriso contido|risadinha curta)\b",
    r"\b(?:digo|pergunto|respondo|falo),?\s+(?:sorrindo|rindo|olhando|segurando|caminhando)\b",
)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def classify_user_message(text: str) -> Engagement:
    value = _normalized(text)
    if not value:
        return "nonsense"
    if any(marker in value for marker in _HOSTILE_MARKERS):
        return "hostile"
    if any(marker in value for marker in _MOCKING_MARKERS):
        return "mocking"
    if value in _DISMISSIVE or (
        len(value.split()) <= 3 and any(value.startswith(marker) for marker in _DISMISSIVE)
    ):
        return "dismissive"
    if value in _MINIMAL or (len(value.split()) == 1 and len(value) <= 5):
        return "minimal"
    if len(value) <= 2 or value in {"...", "???", "kkk", "kkkk", "rs", "rsrs"}:
        return "nonsense"
    return "engaged"


def _first_beat_id(script: PilotScript) -> str:
    configured = str(getattr(script, "first_beat_id", "") or "")
    return configured if configured in script.beats else next(iter(script.beats))


def opening_text(script: PilotScript) -> str:
    beat_id = _first_beat_id(script)
    return _fallback_for_beat(beat_id, script.beats[beat_id])


def decide_turn(script: PilotScript, state: PilotState, user_text: str) -> PilotTurn:
    if state.finished:
        raise RuntimeError("O piloto já foi encerrado.")

    engagement = classify_user_message(user_text)
    updated = PilotState.from_dict(state.to_dict())
    first_beat_id = _first_beat_id(script)
    current_id = state.node_id if state.node_id in script.beats else first_beat_id
    updated.node_id = current_id
    updated.recent_engagement = (updated.recent_engagement + [engagement])[-4:]
    category = script.engagement_policy.get("categories", {}).get(engagement, {})
    updated.desire = max(0, updated.desire + int(category.get("desire_delta", 0) or 0))
    updated.patience = max(0, updated.patience + int(category.get("patience_delta", 0) or 0))

    repeated_bad = sum(
        item in {"dismissive", "nonsense"} for item in updated.recent_engagement[-3:]
    ) >= 2
    if engagement == "hostile":
        return _ending_turn(script, updated, engagement, "end_hostile", user_text)
    if engagement == "mocking":
        ending_id = "end_mocking" if "end_mocking" in script.endings else "end_hostile"
        return _ending_turn(script, updated, engagement, ending_id, user_text)
    if updated.desire <= 0 or updated.patience <= 0 or repeated_bad:
        ending_id = "end_lost_interest" if "end_lost_interest" in script.endings else "end_hostile"
        return _ending_turn(script, updated, engagement, ending_id, user_text)

    current = script.beats[current_id]
    transitions = current.get("on_user") or {}
    normal_target = str(
        transitions.get(engagement)
        or transitions.get("engaged")
        or current.get("terminal_transition")
        or ""
    )
    pending_target = state.pending_next_beat_id if state.pending_next_beat_id else normal_target
    signal = detect_organic_signal(user_text, updated.facts)

    if signal is not None and updated.interstitial_turns < 2:
        updated.facts = signal.facts
        updated.pending_next_beat_id = pending_target
        updated.interstitial_turns += 1
        next_beat = script.beats.get(pending_target)
        next_fallback = _fallback_for_beat(pending_target, next_beat) if next_beat else ""
        prompt = _build_organic_prompt(
            script=script,
            state=updated,
            user_text=user_text,
            signal_kind=signal.kind,
            signal_instruction=signal.instruction,
            next_fallback=next_fallback,
        )
        return PilotTurn(
            engagement=engagement,
            target_id=current_id,
            visible_fallback=signal.fallback,
            system_prompt=prompt,
            state=updated,
        )

    target_id = pending_target
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0

    if target_id in script.endings:
        return _ending_turn(script, updated, engagement, target_id, user_text)

    beat = script.beats.get(target_id)
    if beat is None:
        fallback_ending = "end_lost_interest" if "end_lost_interest" in script.endings else "end_hostile"
        if fallback_ending in script.endings:
            return _ending_turn(script, updated, engagement, fallback_ending, user_text)
        raise KeyError(f"Transição aponta para beat inexistente: {target_id!r}")

    updated.node_id = target_id
    fallback = _fallback_for_beat(target_id, beat)
    prompt = _build_prompt(script, beat, updated, engagement, user_text, fallback)
    terminal = str(beat.get("terminal_transition", "") or "")
    if terminal:
        ending = script.endings[terminal]
        updated.finished = True
        updated.run_status = str(ending.get("run_status", "completed"))
        updated.ending_code = str(ending.get("ending_code", terminal))
        return PilotTurn(
            engagement, target_id, fallback, prompt, updated, True,
            updated.run_status, updated.ending_code,
        )
    return PilotTurn(engagement, target_id, fallback, prompt, updated)


def clean_model_response(response: str, fallback: str) -> str:
    value = response.strip()
    if not value:
        return fallback
    lowered = value.casefold()
    if any(marker.casefold() in lowered for marker in ("<END_RUN", "END_RUN", '"event"', "```json")):
        return fallback
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _FORBIDDEN_NARRATION):
        return fallback
    return value


def _ending_turn(
    script: PilotScript,
    state: PilotState,
    engagement: Engagement,
    ending_id: str,
    user_text: str,
) -> PilotTurn:
    ending = script.endings[ending_id]
    safe_default = _ENDING_FALLBACKS.get(ending_id, "Perdi a vontade. Deixa pra lá.")
    editorial_text = str((ending.get("visible_delivery") or {}).get("text", "")).strip()
    fallback = clean_model_response(editorial_text, safe_default) if editorial_text else safe_default
    final_state = ending.get("mary_final_state") or {}
    state.interest = int(final_state.get("interest", state.interest))
    state.desire = int(final_state.get("desire", state.desire))
    state.node_id = ending_id
    state.finished = True
    state.run_status = str(ending.get("run_status", "terminated"))
    state.ending_code = str(ending.get("ending_code", ending_id))
    prompt = (
        "Você é Mary. Encerre a cena somente com pensamento curto, fala direta ou onomatopeia. "
        "Não descreva movimentos, expressões faciais, postura, olhar, mãos, corpo ou cenário. "
        "Não faça perguntas e não deixe convite para continuar. "
        "Não mencione aplicativo, regras, roteiro ou evento técnico.\n\n"
        f"MENSAGEM DO USUÁRIO: {user_text}\n"
        f"MOTIVO INTERNO: {state.ending_code}\n"
        f"REFERÊNCIA DE VOZ: {fallback}"
    )
    return PilotTurn(
        engagement, ending_id, fallback, prompt, state, True,
        state.run_status, state.ending_code,
    )


def _build_organic_prompt(
    *,
    script: PilotScript,
    state: PilotState,
    user_text: str,
    signal_kind: str,
    signal_instruction: str,
    next_fallback: str,
) -> str:
    bridge = (
        f"PRÓXIMA FALA OBRIGATÓRIA, APENAS SE COUBER NATURALMENTE NESTA RESPOSTA: {next_fallback}"
        if next_fallback
        else "Não antecipe outro movimento nesta resposta."
    )
    return (
        "Você é Mary, uma mulher adulta brasileira, numa história guiada.\n"
        "Este é um TURNO ORGÂNICO INTERMEDIÁRIO. A prioridade é mostrar que Mary ouviu e entendeu o usuário.\n"
        "Não recite mecanicamente a próxima fala do roteiro. Reaja primeiro ao conteúdo novo.\n"
        "Você pode fazer uma ponte curta para o próximo movimento somente quando ela soar espontânea.\n"
        "Não narre ações do usuário nem use terceira pessoa, rubricas ou asteriscos.\n\n"
        f"TIPO DE CONTRIBUIÇÃO: {signal_kind}\n"
        f"INSTRUÇÃO DE REAÇÃO: {signal_instruction}\n"
        f"FATOS CONFIRMADOS: {render_facts(state.facts)}\n"
        f"MENSAGEM DO USUÁRIO: {user_text}\n"
        f"{bridge}"
    )


def _build_prompt(
    script: PilotScript,
    beat: dict[str, Any],
    state: PilotState,
    engagement: Engagement,
    user_text: str,
    fallback: str,
) -> str:
    units = beat.get("units") or []
    unit_text = "\n".join(
        f"- {item.get('kind', 'dialogue')}: "
        f"{item.get('text') or item.get('anchor') or item.get('instruction') or '; '.join(item.get('must_convey', []))}"
        for item in units
        if isinstance(item, dict) and item.get("kind") != "wait_user"
    )
    return (
        "Você é Mary, uma mulher adulta brasileira, numa história guiada.\n"
        "A resposta deve soar como voz viva, não como prosa narrativa.\n\n"
        "REGRAS ABSOLUTAS:\n"
        "- Não narre ações, movimentos, gestos, expressões, postura ou contato visual.\n"
        "- Não use terceira pessoa, rubricas, asteriscos ou parênteses de ação.\n"
        "- Onomatopeia é permitida quando surgir naturalmente na fala.\n"
        "- Não invente ações, pensamentos, endereço, profissão ou passado do usuário.\n"
        "- Siga o movimento atual com máxima fidelidade e não crie outra trama.\n"
        "- Preserve semanticamente a fala canônica, mas adapte ritmo e ligação ao que o usuário disse.\n"
        "- Use fatos confirmados pelo usuário quando forem relevantes.\n"
        "- Não mencione roteiro, classificação, sistema, END_RUN ou JSON.\n\n"
        f"LOCAL: {script.scene.get('location', 'supermercado')}\n"
        f"OBJETIVO ATUAL: {beat.get('objective', '')}\n"
        f"ENGAJAMENTO DETECTADO: {engagement}\n"
        f"FATOS CONFIRMADOS: {render_facts(state.facts)}\n"
        f"RESPOSTA DO USUÁRIO: {user_text}\n\n"
        f"UNIDADES DO MOVIMENTO:\n{unit_text}\n\n"
        f"REFERÊNCIA DE VOZ SEM NARRAÇÃO: {fallback}"
    )


_ENDING_FALLBACKS: dict[str, str] = {
    "end_pilot_positive": "kkkkk... Tchauzinho. E presta atenção, porque da próxima vez a culpa pode ser sua.",
    "end_pilot_neutral": "Bom... desculpa de novo. Vou terminar minhas compras. Tchau.",
    "end_lost_interest": "Perdi a vontade de continuar essa conversa. Deixa pra lá.",
    "end_mocking": "rs... não, obrigada. Perdi o interesse.",
    "end_hostile": "Chega. Não quero mais falar com você.",
}


def _fallback_for_beat(beat_id: str, beat: dict[str, Any] | None) -> str:
    fixed: dict[str, str] = {
        "collision": "Eita, caralho... desculpa! Nossa, como estou distraída.",
        "check_wellbeing": "Ainda bem que você foi educado... Você tá bem? Não machucou?",
        "check_wellbeing_restrained": "Tá tudo bem mesmo?",
        "familiar_face_bridge": "Uau... seu rosto me parece familiar. Você por acaso mora no Plaza?",
        "familiar_face_bridge_restrained": "Seu rosto não me é estranho. Você mora no Plaza?",
        "plaza_response": "Uau... que coincidência. Bom, desculpa de novo pelo esbarrão.",
        "plaza_response_restrained": "Imaginei. Acho que já vi você por lá. Bom, vou terminar minhas compras. Tchau.",
        "confront_low_engagement": "Minha curiosidade está sumindo. Eu estou falando com você, não sozinha.",
        "steer_collision_once": "Eu perguntei porque bati o carrinho em você. Machucou?",
        "steer_wellbeing_once": "Só quero saber se você está bem.",
        "steer_plaza_once": "Perguntei se você mora no Plaza.",
    }
    if beat_id in fixed:
        return fixed[beat_id]
    if not beat:
        return ""

    units = beat.get("units") or []
    for item in units:
        if not isinstance(item, dict) or item.get("kind") == "wait_user":
            continue
        value = item.get("anchor") or item.get("text")
        if value:
            return str(value)
    return "Hummm... vou responder só ao que faz sentido agora."
