from __future__ import annotations

import streamlit as st

from roleplay.engine import StoryEngine
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from roleplay.prompt_builder import build_system_prompt
from roleplay.validator import enforce_movement
from stories import CASADA_FRUSTRADA


MODEL_DEFAULT = "google/gemini-3-flash-preview"


st.set_page_config(page_title="Roleplay 2026", page_icon="💬")
st.title("Roleplay 2026")
st.caption("Motor narrativo novo, determinístico e isolado.")

engine = StoryEngine(CASADA_FRUSTRADA)

if "story_state" not in st.session_state:
    st.session_state.story_state = StoryState()
if "messages" not in st.session_state:
    st.session_state.messages = []

state: StoryState = st.session_state.story_state

with st.sidebar:
    st.subheader("Estado do motor")
    step = engine.current_step(state)
    if step is None:
        st.write("História concluída")
    else:
        st.write(f"Rota: `{step[0]}`")
        st.write(f"Beat: `{step[1]}`")
    st.write(f"Ordens consumidas: `{state.consumed_orders}`")

    if st.button("Reiniciar história", use_container_width=True):
        st.session_state.story_state = StoryState()
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("screenplay_order") is not None:
            st.caption(f"Roteiro: ordem {message['screenplay_order']}")

if state.finished:
    st.success("História concluída.")
    st.stop()

user_text = st.chat_input("Escreva sua mensagem para Mary")
if user_text:
    movement = engine.next_movement(state)
    if movement is None:
        st.session_state.story_state = state
        st.rerun()

    st.session_state.messages.append({"role": "user", "content": user_text})

    api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
    model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()

    raw_response = movement.content
    generation_error = ""

    if api_key:
        history = [
            {"role": item["role"], "content": item["content"]}
            for item in st.session_state.messages[:-1][-12:]
        ]
        try:
            raw_response = generate_response(
                api_key=api_key,
                model=model,
                system_prompt=build_system_prompt(movement=movement),
                history=history,
                user_text=user_text,
            )
        except OpenRouterError as exc:
            generation_error = str(exc)

    final_response, used_fallback = enforce_movement(raw_response, movement)

    # O cursor é atualizado antes do rerun. Nenhum wrapper participa do fluxo.
    updated_state = engine.consume(state, movement)
    st.session_state.story_state = updated_state
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": final_response,
            "screenplay_order": movement.order,
            "screenplay_route": movement.route,
            "screenplay_beat": movement.beat,
            "screenplay_fallback": used_fallback or bool(generation_error),
        }
    )

    if generation_error:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"[Diagnóstico técnico: {generation_error}]",
                "technical": True,
            }
        )

    st.rerun()
