from __future__ import annotations

"""Detecção conservadora de voz em primeira pessoa para roteiros autorais.

Português permite ocultar o pronome ("tive uma ideia", "percebi o olhar").
Por isso, procurar somente "eu" rejeita frases válidas. Esta lista reúne
pronomes e formas verbais frequentes na escrita de beats e pensamentos, sem
recorrer a terminações genéricas que confundiriam substantivos com verbos.
"""

import re
import unicodedata


_TOKEN = re.compile(r"[^\W_]+", flags=re.UNICODE)

_PRONOUNS = {
    "eu", "me", "mim", "meu", "minha", "meus", "minhas", "comigo",
}

_VERBS = {
    # Verbos auxiliares, modais e irregulares comuns.
    "acho", "achei", "consegui", "consigo", "dei", "digo", "disse",
    "estou", "faco", "faria", "fiquei", "fico", "fiz", "fui", "ia",
    "posso", "pude", "pus", "quero", "quis", "sei", "sinto", "sou",
    "tenho", "terei", "teria", "tive", "to", "trouxe", "vejo", "vi",
    "vim", "vou", "vamos",
    # Percepção, pensamento e desejo.
    "adorei", "adoro", "desejei", "desejo", "imagino", "imaginei",
    "noto", "notei", "penso", "pensei", "percebo", "percebi", "reparo",
    "reparei", "senti", "sonho", "sonhei",
    # Movimentos narrativos usuais.
    "aceito", "acolho", "agradeco", "aguardo", "aproximo", "aviso",
    "avistei", "avisto", "caminho", "cheguei", "comeco", "conto",
    "continuei", "continuo", "decidi", "decido", "deixo", "demonstro",
    "desacelero", "descobri", "descubro", "encerro", "encontrei",
    "encontro", "esbarrei", "esbarro", "espero", "explico", "falo",
    "inicio", "mantenho", "mostro", "observo", "olha", "peco", "pergunto",
    "reajo", "reconheci", "reconheco", "recuso", "respondi", "respondo",
    "revelo", "sorrio", "terminei", "termino",
    # Ações e estados frequentes em pensamentos autorais.
    "caio", "entendi", "entendo", "gostaria", "gostei", "gosto",
    "lembrei", "lembro", "preciso", "prefiro", "pretendo", "tento",
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def has_first_person_voice(text: str) -> bool:
    """Reconhece primeira pessoa explícita ou verbo autoral inequívoco."""

    tokens = {_plain(token).casefold() for token in _TOKEN.findall(str(text or ""))}
    return bool(tokens.intersection(_PRONOUNS | _VERBS))


__all__ = ["has_first_person_voice"]
