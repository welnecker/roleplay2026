from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, MutableMapping

from services.first_person import has_first_person_voice


ROTEIROS_COLUMNS = (
    "package_id",
    "script_version",
    "line_id",
    "order",
    "instruction",
    "status",
    "updated_at",
)
_TAG_PATTERN = re.compile(
    r"(?ms)^[ \t]*\[([^\]\n]+)\][ \t]*(.*?)(?=^[ \t]*\[[^\]\n]+\]|\Z)"
)
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_DEPENDENT_KINDS = {"PENSAMENTO", "PENSAMENTO_INTERPRETADO", "FALA", "FALA_INTERPRETADA", "FALA_EXATA", "FALA_EXATA_INTIMA", "FALA_LIVRE", "PONTE"}
_DECISION_COMPONENTS = {"ACEITE", "PROSSEGUIR", "TENTAR", "AVISO", "ENCERRAMENTO"}
_PROFILE_TAGS = {
    "HOMEM", "MULHER", "NEUTRO", "NEUTRA", "CORPO_MASCULINO",
    "CORPO_FEMININO", "CORPO_INTERSEXO",
}


class ScriptAuthoringError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedInstruction:
    header: str
    kind: str
    argument: str
    text: str
    instruction: str


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def slugify(value: str, *, fallback: str = "roteiro") -> str:
    clean = _SLUG_PATTERN.sub("_", _plain(value).casefold()).strip("_")
    return clean or fallback


def package_id_from_title(title: str) -> str:
    return "roleplay2026." + slugify(title, fallback="nova_historia")


def synchronized_package_id(
    title: str, current_package_id: str, previous_suggestion: str = ""
) -> tuple[str, str]:
    """Atualiza a sugestão sem apagar um package_id editado manualmente."""
    suggestion = package_id_from_title(title) if str(title or "").strip() else ""
    current = str(current_package_id or "").strip()
    previous = str(previous_suggestion or "").strip()
    if not current or current == previous:
        current = suggestion
    return current, suggestion


def clear_authoring_state(
    state: MutableMapping[str, Any], *, draft_key: str, rows_key: str
) -> None:
    """Limpa o rascunho antes da recriação dos widgets pelo Streamlit."""
    state[draft_key] = ""
    state.pop(rows_key, None)


def parse_instruction(header: str, text: str) -> ParsedInstruction:
    raw_header = " ".join(str(header or "").strip().split())
    parts = raw_header.split()
    if not parts:
        raise ScriptAuthoringError("Tag vazia.")

    first = _plain(parts[0]).upper()
    argument = " ".join(parts[1:]).strip()
    kind = first
    if first == "FALA":
        normalized_argument = _plain(argument).casefold()
        if normalized_argument == "exata" or normalized_argument.startswith("exata "):
            kind = (
                "FALA_EXATA_INTIMA"
                if normalized_argument == "exata intima"
                or normalized_argument.startswith("exata intima ")
                else "FALA_EXATA"
            )
        elif normalized_argument == "livre" or normalized_argument.startswith("livre "):
            kind = "FALA_LIVRE"
        elif (normalized_argument.split(maxsplit=1)[0] if normalized_argument else "") in {"interpretada", "interpretado", "interpretativa", "interpretativo"}:
            kind = "FALA_INTERPRETADA"
    elif first == "PENSAMENTO":
        normalized_argument = _plain(argument).casefold()
        if (normalized_argument.split(maxsplit=1)[0] if normalized_argument else "") in {"interpretado", "interpretada", "interpretativo", "interpretativa"}:
            kind = "PENSAMENTO_INTERPRETADO"
    elif first == "PATIO":
        normalized_argument = _plain(argument).casefold()
        if normalized_argument.startswith("decisao"):
            kind = "PATIO_DECISAO"
        elif normalized_argument.startswith("final"):
            kind = "PATIO_FINAL"
        else:
            raise ScriptAuthoringError(
                f"Tag não reconhecida: [{raw_header}]."
            )
    elif first == "INTERPRETAR":
        kind = "FALA_INTERPRETADA"
    elif first == "TRANSICAO":
        kind = "TRANSICAO"

    allowed = {
        "CENA",
        "BEAT",
        "PENSAMENTO",
        "PENSAMENTO_INTERPRETADO",
        "FALA",
        "FALA_INTERPRETADA",
        "FALA_EXATA",
        "FALA_EXATA_INTIMA",
        "FALA_LIVRE",
        "PONTE",
        "TRANSICAO",
        "PATIO_FINAL",
        "PATIO_DECISAO",
        "ACEITE",
        "PROSSEGUIR",
        "TENTAR",
        "AVISO",
        "ENCERRAMENTO",
        "FIM",
    }
    if kind not in allowed:
        raise ScriptAuthoringError(f"Tag não reconhecida: [{raw_header}].")

    clean_text = str(text or "").strip()
    instruction = f"[{raw_header}]"
    if clean_text:
        instruction += " " + clean_text
    return ParsedInstruction(raw_header, kind, argument, clean_text, instruction)


def parse_draft(draft: str) -> list[ParsedInstruction]:
    source = str(draft or "").strip()
    if not source:
        raise ScriptAuthoringError("Digite ao menos uma instrução.")

    matches = list(_TAG_PATTERN.finditer(source))
    if not matches:
        raise ScriptAuthoringError("Nenhuma tag de roteiro foi encontrada.")
    prefix = source[: matches[0].start()].strip()
    if prefix:
        raise ScriptAuthoringError("Existe texto antes da primeira tag.")

    parsed = [
        parse_instruction(match.group(1), match.group(2))
        for match in matches
    ]
    consumed = "".join(match.group(0) for match in matches).strip()
    if not consumed:
        raise ScriptAuthoringError("O roteiro não pôde ser interpretado.")
    return parsed


def _unique_line_id(base: str, used: set[str]) -> str:
    candidate = slugify(base)
    suffix = 2
    while candidate in used:
        candidate = f"{slugify(base)}_{suffix:02d}"
        suffix += 1
    used.add(candidate)
    return candidate


def _validate_sequence(items: Iterable[ParsedInstruction]) -> list[str]:
    materialized = list(items)
    errors: list[str] = []
    current_beat = ""
    beat_count = 0
    yard_beat_count = 0
    in_final_yard = False
    has_ending = False
    decision_open = False
    decision_components: set[str] = set()
    decision_ids: set[str] = set()
    ending_codes: set[str] = set()

    def close_decision() -> None:
        nonlocal decision_open, decision_components
        if not decision_open:
            return
        missing = _DECISION_COMPONENTS - decision_components
        if missing:
            errors.append(
                "Pátio decisório incompleto: " + ", ".join(sorted(missing))
            )
        decision_open = False
        decision_components = set()

    for index, item in enumerate(materialized, start=1):
        if item.kind == "BEAT":
            close_decision()
            beat_count += 1
            current_beat = f"beat_{beat_count}"
            if in_final_yard:
                yard_beat_count += 1
        elif item.kind in _DEPENDENT_KINDS and not current_beat:
            errors.append(f"Linha autoral {index}: [{item.header}] precisa de [BEAT] anterior.")
        elif item.kind == "PATIO_FINAL":
            close_decision()
            current_beat = ""
            in_final_yard = True
        elif item.kind == "CENA":
            close_decision()
            current_beat = ""
        elif item.kind == "TRANSICAO":
            close_decision()
            current_beat = ""
        elif item.kind == "PATIO_DECISAO":
            if not current_beat:
                errors.append(f"Linha autoral {index}: [PÁTIO DECISÃO] precisa de [BEAT] anterior.")
            if decision_open:
                errors.append(f"Linha autoral {index}: um beat não pode possuir dois pátios decisórios.")
            decision_id = " ".join(item.argument.split()[1:]).strip()
            if not decision_id:
                errors.append(f"Linha autoral {index}: [PÁTIO DECISÃO] exige id.")
            elif decision_id in decision_ids:
                errors.append(f"Linha autoral {index}: decision_id duplicado: {decision_id}.")
            decision_ids.add(decision_id)
            decision_open = True
            decision_components = set()
        elif item.kind in _DECISION_COMPONENTS:
            if not decision_open:
                errors.append(f"Linha autoral {index}: [{item.header}] exige [PÁTIO DECISÃO] anterior.")
            elif item.kind in decision_components:
                errors.append(f"Linha autoral {index}: [{item.header}] duplicado no pátio.")
            decision_components.add(item.kind)
            if item.kind == "ENCERRAMENTO":
                code = item.argument.strip()
                if not code:
                    errors.append(f"Linha autoral {index}: [ENCERRAMENTO] exige código.")
                elif code in ending_codes:
                    errors.append(f"Linha autoral {index}: código duplicado: {code}.")
                ending_codes.add(code)
        elif item.kind == "FIM":
            close_decision()
            has_ending = True

        if item.kind in {"BEAT", "PONTE", "PATIO_FINAL"}:
            if item.text and not has_first_person_voice(item.text):
                errors.append(
                    f"Linha autoral {index}: [{item.header}] deve ser escrita em primeira pessoa."
                )

    close_decision()
    if beat_count == 0:
        errors.append("O roteiro precisa ter ao menos um [BEAT].")
    if not has_ending:
        errors.append("O roteiro precisa terminar com [FIM código].")
    if in_final_yard and yard_beat_count < 2:
        errors.append("[PÁTIO FINAL] precisa conter pelo menos dois [BEAT].")
    if materialized and materialized[-1].kind != "FIM":
        errors.append("[FIM código] deve ser a última instrução.")
    return errors


def _profile_suffix(item: ParsedInstruction) -> str:
    argument = _plain(item.argument).upper().split()
    if item.kind in {"FALA_EXATA", "FALA_LIVRE", "FALA_INTERPRETADA", "PENSAMENTO_INTERPRETADO"} and argument:
        argument = argument[1:]
    profile_tag = "_".join(argument)
    if profile_tag == "NEUTRO":
        profile_tag = "NEUTRA"
    return profile_tag.casefold() if profile_tag in _PROFILE_TAGS else ""


def compile_draft_rows(
    draft: str,
    *,
    package_id: str,
    script_version: str,
    initial_block_id: str,
    start_order: int = 10,
    order_step: int = 10,
) -> list[dict[str, object]]:
    clean_package = str(package_id or "").strip()
    clean_version = str(script_version or "").strip()
    if not clean_package.startswith("roleplay2026.") or clean_package.endswith("."):
        raise ScriptAuthoringError(
            "package_id deve seguir o formato roleplay2026.nome_da_historia."
        )
    if not clean_version:
        raise ScriptAuthoringError("Informe a script_version.")
    if int(start_order) < 0 or int(order_step) <= 0:
        raise ScriptAuthoringError("A ordem inicial deve ser positiva e o intervalo maior que zero.")

    items = parse_draft(draft)
    errors = _validate_sequence(items)
    if errors:
        raise ScriptAuthoringError("\n".join(errors))

    current_block = slugify(initial_block_id, fallback="roteiro")
    current_beat = ""
    beat_number = 0
    transition_number = 0
    used: set[str] = set()
    rows: list[dict[str, object]] = []

    for index, item in enumerate(items):
        if item.kind == "CENA":
            current_block = slugify(item.argument or current_block)
            line_id = _unique_line_id(f"{current_block}_cena", used)
            current_beat = ""
        elif item.kind == "PATIO_FINAL":
            current_block = slugify(
                item.argument.removeprefix("FINAL").strip() or "patio_final"
            )
            line_id = _unique_line_id(f"{current_block}_patio_final", used)
            current_beat = ""
        elif item.kind == "BEAT":
            beat_number += 1
            current_beat = f"{current_block}_{beat_number:03d}"
            line_id = _unique_line_id(current_beat, used)
        elif item.kind in {"PENSAMENTO", "PENSAMENTO_INTERPRETADO"}:
            suffix = _profile_suffix(item)
            base = f"{current_beat}_pensamento"
            line_id = _unique_line_id(f"{base}_{suffix}" if suffix else base, used)
        elif item.kind in {"FALA", "FALA_INTERPRETADA", "FALA_EXATA", "FALA_EXATA_INTIMA", "FALA_LIVRE"}:
            suffix = _profile_suffix(item)
            base = f"{current_beat}_fala"
            line_id = _unique_line_id(f"{base}_{suffix}" if suffix else base, used)
        elif item.kind == "PONTE":
            line_id = _unique_line_id(f"{current_beat}_ponte", used)
        elif item.kind == "TRANSICAO":
            transition_number += 1
            line_id = _unique_line_id(
                f"{current_block}_transicao_{transition_number:03d}", used
            )
            current_beat = ""
        elif item.kind == "FIM":
            line_id = _unique_line_id(f"{current_block}_fim", used)
        else:
            line_id = _unique_line_id(f"{current_block}_linha_{index + 1:03d}", used)

        rows.append(
            {
                "package_id": clean_package,
                "script_version": clean_version,
                "line_id": line_id,
                "order": int(start_order) + index * int(order_step),
                "instruction": item.instruction,
                "status": "active",
                "updated_at": "",
            }
        )
    return rows


def rows_to_delimited(rows: Iterable[dict[str, object]], *, delimiter: str) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ROTEIROS_COLUMNS, delimiter=delimiter)
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in ROTEIROS_COLUMNS})
    return output.getvalue()


def rows_to_tsv(rows: Iterable[dict[str, object]]) -> str:
    return rows_to_delimited(rows, delimiter="\t")


def rows_to_csv(rows: Iterable[dict[str, object]]) -> str:
    return "\ufeff" + rows_to_delimited(rows, delimiter=";")


__all__ = [
    "ROTEIROS_COLUMNS",
    "ScriptAuthoringError",
    "clear_authoring_state",
    "compile_draft_rows",
    "package_id_from_title",
    "parse_draft",
    "rows_to_csv",
    "rows_to_tsv",
    "slugify",
    "synchronized_package_id",
]