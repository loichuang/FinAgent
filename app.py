"""Demo of FinAgent: ask a question about the 10-K filings, see the answer and the tool calls.

Run locally: .venv/bin/python -m streamlit run app.py
Online on Streamlit Community Cloud, with the API key as the secret LLM_API_KEY.
"""
import threading
from datetime import date

import streamlit as st

from finagent.agent import ask
from finagent.demo import DEMO_CACHE, EXAMPLES, QUESTIONS_PER_DAY, QUESTIONS_PER_VISITOR


@st.cache_resource
def daily_count() -> dict:
    """One counter shared by every visitor: cache_resource builds this dict once per server
    process, while session_state is per browser tab. It restarts at 0 when the app restarts,
    which the spend limit of the Anthropic Console covers."""
    return {"day": date.today(), "count": 0, "lock": threading.Lock()}


def take_daily_slot() -> bool:
    """Count one free-text question for today, or say False when the day's quota is used."""
    counter = daily_count()
    with counter["lock"]:                       # two visitors may ask at the same instant
        if counter["day"] != date.today():      # a new day: the quota starts again
            counter["day"], counter["count"] = date.today(), 0
        if counter["count"] >= QUESTIONS_PER_DAY:
            return False
        counter["count"] += 1
        return True


def show_answer(answer: dict) -> None:
    """Draw one answer of ask() on the page.

    The dict holds: answer (the sentence), value (the figure, or None when the agent abstains),
    unit, fiscal_year, tool_calls (name, input, is_error of each call) and _usage (tokens,
    turns, cached).
    """
    st.write(answer["answer"])
    # The proof that the figure comes from the data: one readable line per tool call, folded
    calls = answer["tool_calls"]
    with st.expander(f"Tool calls ({len(calls)})"):
        for call in calls:
            arguments = " · ".join(f"{key}: {value}" for key, value in call["input"].items())
            failed = " · *failed*" if call["is_error"] else ""   # only a failed call is marked
            st.markdown(f"`{call['name']}` · {arguments}{failed}")
    # What the answer cost, in small grey print
    usage = answer["_usage"]
    cost = (f"{usage['turns']} turns · {usage['input_tokens']:,} input tokens · "
            f"{usage['output_tokens']:,} output tokens")
    if usage["cached"]:
        cost += " · from cache"
    st.caption(cost)


# 1. Tab, title, what can be asked, and the history kept across reruns
st.set_page_config(page_title="FinAgent", page_icon=":material/bar_chart:")  # first st call
st.title("FinAgent")
st.caption("Figures and ratios from the 10-K filings of Apple, Amazon, Alphabet, Microsoft "
           "and Nvidia. Each question is answered on its own.")
if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.asked = 0      # free-text questions of this visitor

# Example questions: their answers are committed (data/demo_cache.jsonl), so they cost nothing
# and do not count against the limits
example = None
for column, text in zip(st.columns(len(EXAMPLES)), EXAMPLES):
    if column.button(text, width="stretch"):
        example = text

# 2. Draw the history again: the rerun has wiped the page
for role, content in st.session_state.history:
    with st.chat_message(role):
        if role == "user":
            st.write(content)        # content is the question
        else:
            show_answer(content)     # content is the dict of ask()

# 3. Read the chat box: a question only on the rerun where it was sent. Closed once this
# visitor has used their free-text questions
left = QUESTIONS_PER_VISITOR - st.session_state.asked
question = st.chat_input(
    f"Ask for a figure or a ratio, e.g. Apple's ROIC in fiscal 2024 ({left} questions left)"
    if left > 0 else "No questions left in this session: try the examples above",
    disabled=left <= 0)

# 4. A new question: show it, ask the agent once (spinner, try/except), show the answer.
# An example is read from its cache; a free-text question first takes a slot of the day's
# quota, counted before the call so that a failed call is counted too
if example or question:
    question = example or question
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            if example:
                answer = ask(question, cache=DEMO_CACHE)
            elif not take_daily_slot():
                raise RuntimeError("the demo has answered its questions for today, "
                                   "come back tomorrow or try the examples above")
            else:
                st.session_state.asked += 1
                with st.spinner("The agent is reading the filings..."):
                    answer = ask(question)   # the only call to the model, once per question
        except Exception as error:
            # A refusal, an answer cut off, no answer after the last turn: said, not crashed
            st.error(f"No answer: {type(error).__name__}: {error}")
        else:
            show_answer(answer)
            # 5. Keep the question and the answer in the history, for the next reruns
            st.session_state.history.append(("user", question))
            st.session_state.history.append(("assistant", answer))
            # Draw the page again from the history, so that the chat box shows the new count
            st.rerun()

