import os
import time
import re

import streamlit as st
from openai import OpenAI


# ===========================
#   OPENAI КЛЮЧ
# ===========================
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

client = OpenAI()

ASSISTANT_ID = "asst_ZvWnvao1k3BaN9Mf4UfsKBca"


# ===========================
#   ДОПОМІЖНІ ФУНКЦІЇ
# ===========================

def get_or_create_thread_id() -> str:
    """Створює або повертає thread_id."""
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


def add_message_to_thread(thread_id: str, user_text: str) -> None:
    """Додає повідомлення користувача в Thread."""
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text
    )


def run_assistant(thread_id: str) -> None:
    """Запускає Assistant і чекає завершення Run."""

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
        tool_choice={"type": "file_search"},
    )

    while True:
        status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

        if status.status == "completed":
            return

        if status.status in ("failed", "cancelled", "expired"):

            # Отримуємо технічну помилку (лише для розробника)
            err_obj = getattr(status, "last_error", None)

            if err_obj:
                print(
                    "\n[OPENAI RUN ERROR]",
                    f"\nStatus: {status.status}",
                    f"\nCode: {getattr(err_obj, 'code', None)}",
                    f"\nMessage: {getattr(err_obj, 'message', None)}\n"
                )
            else:
                print(f"[OPENAI RUN ERROR] Status={status.status}, last_error=None")

            raise RuntimeError("run_failed")

        time.sleep(1)


def get_last_assistant_message(thread_id: str) -> str:
    """Читає останнє повідомлення Assistant’а."""
    msgs = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=1,
    )

    if not msgs.data:
        return "Не вдалося отримати відповідь від асистента."

    msg = msgs.data[0]
    parts = []

    for block in msg.content:
        if block.type == "text":
            parts.append(block.text.value)

    return "\n".join(parts).strip()


def clean_citations(text: str) -> str:
    """Прибирає службові посилання на джерела."""
    text = re.sub(r"【.*?†.*?】", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# ===========================
#   STREAMLIT ІНТЕРФЕЙС
# ===========================

st.set_page_config(page_title="Експерт з сертифікації послуг охорони", layout="wide")

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.write(
    "Постав запитання щодо порядку сертифікації послуг охорони,\n"
    "ДСТУ CLC/TS 50131-7:2014, ДСТУ EN 16763-2017 та ДСТУ 4030-2001."
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# --- КНОПКА НОВОЇ КОНСУЛЬТАЦІЇ ---
with st.sidebar:
    if st.button("🔁 Почати нову консультацію"):
        st.session_state.chat_messages = []
        st.session_state.pop("thread_id", None)
        st.success("Контекст очищено. Можеш ставити нові запитання.")


# --- ВІДОБРАЖЕННЯ ІСТОРІЇ ---
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --- ВВІД КОРИСТУВАЧА ---
user_input = st.chat_input("Напиши запитання…")

if user_input:

    # показуємо в UI
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        thread_id = get_or_create_thread_id()
        add_message_to_thread(thread_id, user_input)

        with st.chat_message("assistant"):
            with st.spinner("Опрацьовую запитання…"):
                run_assistant(thread_id)
                response = get_last_assistant_message(thread_id)
                response = clean_citations(response)
                st.markdown(response)

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )

    except Exception:
        # Логуємо тільки в бекенд
        print("[APP ERROR] Assistant run failed")

        # Користувач бачить тільки нейтральне
        user_msg = (
            "Сталася технічна помилка під час обробки запиту. "
            "Спробуй, будь ласка, ще раз трохи пізніше."
        )

        with st.chat_message("assistant"):
            st.error(user_msg)

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": user_msg}
        )
