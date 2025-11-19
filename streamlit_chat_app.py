import os
import time
import re
import traceback

import streamlit as st
from openai import OpenAI


# ===========================
#   OPENAI КЛЮЧ
# ===========================
# Ключ беремо зі Streamlit secrets, а не з коду
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# Клієнт OpenAI (асистенти v2)
client = OpenAI()

# ID асистента з Platform (той, де підв'язаний Vector Store)
ASSISTANT_ID = "asst_ZvWnvao1k3BaN9Mf4UfsKBca"


# ===========================
#   ДОПОМІЖНІ ФУНКЦІЇ
# ===========================

def get_or_create_thread_id() -> str:
    """
    Створює новий або повертає існуючий thread_id.
    Thread зберігаємо в session_state, щоб був один діалог.
    """
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        print(f"[THREAD] Створено новий thread: {thread.id}")
    return st.session_state.thread_id


def add_message_to_thread(thread_id: str, user_text: str) -> None:
    """
    Додає повідомлення користувача в Thread асистента.
    """
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text,
    )
    print(f"[THREAD] Додано повідомлення користувача в thread {thread_id}")


def run_assistant(thread_id: str) -> None:
    """
    Запускає асистента і чекає завершення Run.
    Якщо Run завершується зі статусом failed / cancelled / expired –
    логуються деталі і кидається RuntimeError("run_failed").
    """

    # Старт Run: примусово вимагаємо file_search
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
        tool_choice={"type": "file_search"},
    )

    print(f"[RUN] Старт run: {run.id} для thread: {thread_id}")

    while True:
        status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )

        # Для дебагу можна дивитися статуси у логах
        print(f"[RUN] run_id={run.id}, status={status.status}")

        if status.status == "completed":
            print(f"[RUN] run_id={run.id} успішно завершено")
            return

        if status.status in ("failed", "cancelled", "expired"):
            # last_error приходить від OpenAI, якщо є технічна помилка
            err_obj = getattr(status, "last_error", None)

            if err_obj:
                print(
                    "\n[OPENAI RUN ERROR]",
                    f"\n  Status:  {status.status}",
                    f"\n  Code:    {getattr(err_obj, 'code', None)}",
                    f"\n  Message: {getattr(err_obj, 'message', None)}\n",
                )
            else:
                print(f"[OPENAI RUN ERROR] Status={status.status}, last_error=None")

            # Це перехопить зовнішній try/except і покаже юзеру нейтральне повідомлення
            raise RuntimeError("run_failed")

        # Якщо ще в процесі – чекаємо
        time.sleep(1)


def get_last_assistant_message(thread_id: str) -> str:
    """
    Читає останнє повідомлення асистента з Thread.
    """
    msgs = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=1,
    )

    if not msgs.data:
        return "Не вдалося отримати відповідь від асистента."

    msg = msgs.data[0]
    parts: list[str] = []

    for block in msg.content:
        if block.type == "text":
            parts.append(block.text.value)

    return "\n".join(parts).strip()


def clean_citations(text: str) -> str:
    """
    Прибирає службові посилання вигляду 【...†source】,
    щоб відповіді виглядали охайно.
    """
    text = re.sub(r"【.*?†.*?】", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# ===========================
#   STREAMLIT ІНТЕРФЕЙС
# ===========================

st.set_page_config(
    page_title="Експерт з сертифікації послуг охорони",
    layout="wide",
)

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.write(
    "Постав запитання щодо порядку сертифікації послуг охорони, "
    "ДСТУ CLC/TS 50131-7:2014, ДСТУ EN 16763-2017 та ДСТУ 4030-2001."
)

# Історія чату зберігається в session_state
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# --- КНОПКА НОВОЇ КОНСУЛЬТАЦІЇ ---
with st.sidebar:
    if st.button("🔁 Почати нову консультацію"):
        st.session_state.chat_messages = []
        st.session_state.pop("thread_id", None)
        st.success("Контекст очищено. Можеш ставити нові запитання.")
        print("[UI] Контекст очищено, thread_id видалено")


# --- ВІДОБРАЖЕННЯ ІСТОРІЇ ---
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --- ВВІД КОРИСТУВАЧА ---
user_input = st.chat_input("Напиши запитання…")

if user_input:
    # 1. Показуємо питання користувача в UI і зберігаємо в історії
    st.session_state.chat_messages.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        # 2. Отримуємо або створюємо thread, додаємо повідомлення
        thread_id = get_or_create_thread_id()
        add_message_to_thread(thread_id, user_input)

        # 3. Запускаємо асистента
        with st.chat_message("assistant"):
            with st.spinner("Опрацьовую запитання…"):
                run_assistant(thread_id)
                raw_response = get_last_assistant_message(thread_id)
                response = clean_citations(raw_response)
                st.markdown(response)

        # 4. Зберігаємо відповідь в історії
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )

    except Exception as e:
        # --- ЛОГИ ДЛЯ РОЗРОБНИКА ---
        # Повний стек помилки в логах Streamlit
        print("\n[APP ERROR] Assistant run failed")
        print(repr(e))
        traceback.print_exc()
        print("----------\n")

        # --- ПОВІДОМЛЕННЯ ДЛЯ КОРИСТУВАЧА ---
        user_msg = (
            "Сталася технічна помилка під час обробки запиту. "
            "Спробуй, будь ласка, ще раз трохи пізніше."
        )

        with st.chat_message("assistant"):
            st.error(user_msg)

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": user_msg}
        )
