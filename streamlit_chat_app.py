import os
import time
import re
import traceback

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
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


def add_message_to_thread(thread_id: str, user_text: str) -> None:
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
        # ❗ Прибрано tool_choice — він часто ламає Run
    )

    while True:
        status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

        if status.status == "completed":
            return

        if status.status in ("failed", "cancelled", "expired"):
            err_obj = getattr(status, "last_error", None)

            print("\n====== OPENAI RUN ERROR ======")
            print(f"Status: {status.status}")
            print(f"Run ID: {run.id}")
            print(f"Thread ID: {thread_id}")

            if err_obj:
                print(f"Code: {err_obj.code}")
                print(f"Message: {err_obj.message}")
            else:
                print("last_error = None")

            print("=================================\n")

            raise RuntimeError("run_failed")

        time.sleep(1)


def get_last_assistant_message(thread_id: str) -> str:
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
    text = re.sub(r"【.*?†.*?】", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# ===========================
#   STREAMLIT UI
# ===========================

st.set_page_config(page_title="Експерт з сертифікації послуг охорони", layout="wide")

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.write(
    "Постав запитання щодо порядку сертифікації послуг охорони,\n"
    "ДСТУ CLC/TS 50131-7:2014, ДСТУ EN 16763-2017 та ДСТУ 4030-2001."
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


with st.sidebar:
    if st.button("🔁 Почати нову консультацію"):
        st.session_state.chat_messages = []
        st.session_state.pop("thread_id", None)
        st.success("Контекст очищено.")


for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


user_input = st.chat_input("Напиши запитання…")

if user_input:

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

    except Exception as e:
        # 🔥 ПОВНИЙ ТРЕЙСБЕК ДЛЯ РОЗРОБНИКА
        print("\n====== APP CRASH ======")
        print(traceback.format_exc())
        print("========================\n")

        user_msg = (
            "Сталася технічна помилка під час обробки запиту. "
            "Спробуй, будь ласка, ще раз трохи пізніше."
        )

        with st.chat_message("assistant"):
            st.error(user_msg)

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": user_msg}
        )
