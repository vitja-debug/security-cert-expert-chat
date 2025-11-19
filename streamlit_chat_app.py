import os
import time
import re  # для очищення технічних посилань

import streamlit as st
from openai import OpenAI

# 1. Підтягуємо API-ключ зі Streamlit Secrets (НЕ з коду)
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# 2. Створюємо клієнта OpenAI (ключ береться з env)
client = OpenAI()

# 3. ID твого Assistant з файлами ДСТУ/EN
ASSISTANT_ID = "asst_ZvWnvao1k3BaN9Mf4UfsKBca"


# -------------------- Допоміжні функції -------------------- #

def get_or_create_thread_id() -> str:
    """Зберігаємо thread_id в сесії, щоб контекст діалогу не губився."""
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


def add_message_to_thread(thread_id: str, user_text: str) -> None:
    """Додаємо повідомлення користувача в thread Assistant’а."""
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text,
    )


def run_assistant(thread_id: str) -> None:
    """
    Запускаємо Assistant і чекаємо завершення run’а.

    ВАЖЛИВО:
    Примусово вимагаємо використання інструмента file_search,
    щоб відповіді ґрунтувалися на документах (vector store),
    а не на загальних знаннях моделі.
    """
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
        tool_choice={"type": "file_search"},
    )

    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )

        if run_status.status == "completed":
            return

        if run_status.status in ("failed", "cancelled", "expired"):
            # Пробуємо зчитати деталі помилки від OpenAI
            err = getattr(run_status, "last_error", None)
            if err is not None:
                # Лог для розробника (в логи бекенду / консоль)
                print(
                    f"[OpenAI RUN ERROR] status={run_status.status}, "
                    f"code={getattr(err, 'code', None)}, "
                    f"message={getattr(err, 'message', None)}"
                )
                raise RuntimeError(
                    f"Run ended with status: {run_status.status}, "
                    f"code={getattr(err, 'code', None)}, "
                    f"message={getattr(err, 'message', None)}"
                )
            else:
                print(f"[OpenAI RUN ERROR] status={run_status.status}, no last_error")
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


def clean_citations(text: str) -> str:
    """
    Прибираємо технічні посилання виду 【...†source】,
    щоб відповідь виглядала професійно.
    """
    # видаляємо конструкції між 【 і 】 з символом † всередині
    text = re.sub(r"【.*?†.*?】", "", text)
    # прибираємо зайві пробіли, що могли з’явитися
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# -------------------- UI Streamlit -------------------- #

st.set_page_config(
    page_title="Експерт з сертифікації послуг охорони",
    layout="wide",
)

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.write(
    "Постав запитання щодо порядку сертифікації послуг охорони, "
    "ДСТУ CLC/TS 50131-7:2014, ДСТУ EN 16763-2017 та ДСТУ 4030-2001."
)

# Ініціалізуємо сховище повідомлень у сесії
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []  # список словників {role, content}

# Кнопка скинути діалог (очищає контекст і thread)
with st.sidebar:
    if st.button("🔁 Почати нову консультацію"):
        st.session_state.chat_messages = []
        st.session_state.pop("thread_id", None)
        st.success("Контекст очищено. Можеш ставити нові запитання.")

# Відображення історії діалогу
for msg in st.session_state.chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])

# Поле вводу користувача
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
                answer = clean_citations(answer)
                st.markdown(answer)

        # Зберігаємо відповідь в історії
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": answer}
        )

    except Exception as e:
        # Логуємо технічні деталі тільки в консоль / бекенд, щоб ти міг їх бачити
        print(f"[APP ERROR] {repr(e)}")

        # А користувачу показуємо нейтральне повідомлення без деталей
        user_friendly_error = (
            "Сталася технічна помилка під час обробки запиту. "
            "Спробуй, будь ласка, ще раз трохи пізніше."
        )

        with st.chat_message("assistant"):
            st.error(user_friendly_error)

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": user_friendly_error}
        )
