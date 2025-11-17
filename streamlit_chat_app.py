import os
import time

import streamlit as st
from openai import OpenAI

# 1. Підтягуємо API-ключ зі Streamlit Secrets (НЕ з коду)
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# 2. Створюємо клієнта OpenAI (ключ береться з env)
client = OpenAI()

# 3. ID твого Assistant з файлами ДСТУ/EN
ASSISTANT_ID = "asst_fV4U4hV81cxyROLvOGyPXWku"


# -------------------- Допоміжні функції -------------------- #

def get_or_create_thread_id():
    """Зберігаємо thread_id в сесії, щоб контекст діалогу не губився."""
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


def add_message_to_thread(thread_id: str, user_text: str):
    """Додаємо повідомлення користувача в thread Assistant’а."""
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text,
    )


def run_assistant(thread_id: str):
    """Запускаємо Assistant і чекаємо завершення run’а."""
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
    )

    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )

        if run_status.status == "completed":
            return

        if run_status.status in ("failed", "cancelled", "expired"):
            raise RuntimeError(f"Run ended with status: {run_status.status}")

        time.sleep(1)


def get_last_assistant_message(thread_id: str) -> str:
    """Дістаємо останню відповідь Assistant’а як текст."""
    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=1,
    )

    if not messages.data:
        return "Не вдалося отримати відповідь від асистента."

    msg = messages.data[0]
    text_parts = []
    for item in msg.content:
        if item.type == "text":
            text_parts.append(item.text.value)
    return "\n".join(text_parts).strip()


# -------------------- UI Streamlit -------------------- #

st.set_page_config(page_title="Експерт з сертифікації послуг охорони", layout="wide")

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.write(
    "Постав запитання щодо ДСТУ 4030, ДСТУ CLC_TS 50131-7, ДСТУ EN 16763 "
    "та пов’язаних вимог до послуг охорони. Я використовую завантажені стандарти в Assistant’і OpenAI."
)

# Ініціалізуємо сховище повідомлень у сесії
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []  # список словників {role, content}


# Відображення історії діалогу
for msg in st.session_state.chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])

# Поле вводу користувача (новий формат chat_input)
user_input = st.chat_input("Напиши запитання…")

if user_input:
    # Показуємо повідомлення користувача в UI
    st.session_state.chat_messages.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        thread_id = get_or_create_thread_id()
        add_message_to_thread(thread_id, user_input)
        with st.chat_message("assistant"):
            with st.spinner("Опрацьовую запитання за стандартами…"):
                run_assistant(thread_id)
                answer = get_last_assistant_message(thread_id)
                st.markdown(answer)

        # Зберігаємо відповідь в історії
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": answer}
        )

    except Exception as e:
        error_text = (
            "Виникла помилка під час звернення до OpenAI API. "
            "Спробуй ще раз пізніше або перевір налаштування ключа/Assistant’а.\n\n"
            f"Деталі: `{e}`"
        )
        with st.chat_message("assistant"):
            st.error(error_text)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": error_text}
        )
