import os
import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ASSISTANT_ID = "asst_XXXXXXXXXXXXXXXXXXXXXXXX"  # заміни на свій ID асистента

st.set_page_config(page_title="Експерт з сертифікації послуг охорони")

st.title("Експерт з сертифікації послуг охорони (ДСТУ)")
st.caption("Постав запитання щодо ДСТУ 4030, ДСТУ CLC_TS 50131-7, ДСТУ EN 16763.")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state["thread_id"] = thread.id

thread_id = st.session_state["thread_id"]

def ask_assistant(user_message: str) -> str:
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message,
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
    )

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    last_message = messages.data[0]

    text = ""
    for p in last_message.content:
        if p.type == "text":
            text += p.text.value

    return text

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Напиши запитання…"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Думаю над відповіддю…"):
            answer = ask_assistant(prompt)
            st.markdown(answer)

    st.session_state["messages"].append({"role": "assistant", "content": answer})
