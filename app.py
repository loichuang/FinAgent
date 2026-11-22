"""Local demo of FinAgent: ask a question about the 10-K filings, see the answer and the tool calls.

Run: .venv/bin/python -m streamlit run app.py
"""
import streamlit as st

from finagent.agent import ask


def show_answer(answer: dict) -> None:
    """Draw one answer of ask() on the page.

    The dict holds: answer (the sentence), value (the figure, or None when the agent abstains),
    unit, fiscal_year, tool_calls (name, input, is_error of each call) and _usage (tokens,
    turns, cached).
    """
    st.write(answer["answer"])
    st.markdown(f"**Used Tool:** {answer["tool_calls"]}")
    st.caption(f"Ressources used : {answer["_usage"]}")


# 1. Title, and the history kept across reruns
st.title("FinAgent - Your Assistant in Finance to read annual report")
if "history" not in st.session_state:
    st.session_state.history = []

# 2. Draw the history again: the rerun has wiped the page
for role, content in st.session_state.history:
    with st.chat_message(role):
        if role == "user":
            st.write(content)        # content is the question
        else:
            show_answer(content)     # content is the dict of ask()

# 3. Read the chat box: a question only on the rerun where it was sent
question = st.chat_input("What is your question")

# 4. A new question: show it, ask the agent once (spinner, try/except), show the answer
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("The agent is reading the filings..."):
                answer = ask(question)       # the only call to the model, once per question
        except Exception as error:
            # A refusal, an answer cut off, no answer after the last turn: said, not crashed
            st.error(f"No answer: {type(error).__name__}: {error}")
        else:
            show_answer(answer)
            # 5. Keep the question and the answer in the history, for the next reruns
            st.session_state.history.append(("user", question))
            st.session_state.history.append(("assistant", answer))

