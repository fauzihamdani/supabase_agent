"""
LangGraph agent:
  1. Node 'router' -> classifies whether the user's message is related to
     retrieving/searching project data. If not, it's refused immediately.
  2. Node 'agent' -> LLM (Groq) with the query_projects tool, can call tools
     multiple times until done (ReAct-style loop via LangGraph).
  3. Node 'tools' -> executes the read-only tool.
"""
import os
import json
from typing import Annotated, Literal, TypedDict
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from tools import TOOLS

load_dotenv()

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

REFUSAL_TEXT = (
    "Sorry, this chat is only for retrieving/searching project data from the database. "
    "Please ask something related to project data, e.g.: search projects, "
    "filter by status, filter by member, or filter by deadline date."
)

SYSTEM_PROMPT = """
You are a data-retrieval agent for the 'projects' table in Supabase.

STRICT RULES:
1. You may ONLY answer questions related to retrieving/searching/filtering project data.
2. You may NEVER insert, update, or delete data. You only have read-only tool access.
3. You must NEVER fabricate/hallucinate data. Every fact MUST come from
   calling the query_projects tool. If the tool returns an empty list, say the data was not found
   — never make up data.
4. If the user asks for something unrelated to project data retrieval
   (e.g. general chit-chat, code requests, opinions, etc.), politely decline and redirect
   back to your main function.
5. Always use the query_projects tool to fetch data, never answer from memory.
6. NEVER write raw data as JSON, a code block, or an array in your answer.
   NEVER state or estimate the number/count of results yourself — the exact count
   is already shown separately by the system. Just briefly describe what was
   searched for, e.g. "Here are the on-hold projects assigned to Fauzi Hamdani."
   Don't list individual project names/ids/details unless the user explicitly
   asks for only 1-3 specific items to be named.
7. Reply in the same language the user used, briefly and clearly.
"""

llm = ChatGroq(model=GROQ_MODEL, temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)

# Second, lightweight LLM specifically for intent classification (guardrail)
router_llm = ChatGroq(model=GROQ_MODEL, temperature=0)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def router_node(state: AgentState) -> Literal["agent", "refuse"]:
    last_user_msg = None
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            last_user_msg = m.content
            break

    classification_prompt = f"""Classify the following user message into one of two labels:
- DATA_QUERY: if the message is related to requesting/searching/filtering/reporting project data
  (name, status, member, date/deadline, export, etc.), including follow-up questions
  that are still within the context of project data.
- OTHER: if the message is not related at all to retrieving project data
  (small talk, code requests, opinions, general topics, etc.).

Reply with ONLY one word: DATA_QUERY or OTHER.

User message: \"\"\"{last_user_msg}\"\"\""""

    result = router_llm.invoke([HumanMessage(content=classification_prompt)])
    label = (result.content or "").strip().upper()
    return "agent" if "DATA_QUERY" in label else "refuse"


def agent_node(state: AgentState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def refuse_node(state: AgentState):
    return {"messages": [AIMessage(content=REFUSAL_TEXT)]}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "end"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("refuse", refuse_node)

    graph.set_conditional_entry_point(
        router_node,
        {"agent": "agent", "refuse": "refuse"},
    )

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("refuse", END)

    return graph.compile()


APP_GRAPH = build_graph()


def run_agent(user_message: str, history: list[dict] | None = None) -> dict:
    """
    history: optional list of {"role": "user"|"assistant", "content": str}, for multi-turn.
    Returns dict: {"reply": str, "tool_results": [...]} -- tool_results is collected so
    the FE can use the data directly (e.g. to render a table / trigger export).
    """
    msgs: list[AnyMessage] = []
    for h in (history or []):
        if h["role"] == "user":
            msgs.append(HumanMessage(content=h["content"]))
        else:
            msgs.append(AIMessage(content=h["content"]))
    msgs.append(HumanMessage(content=user_message))

    final_state = APP_GRAPH.invoke({"messages": msgs})

    seen = {}
    for m in final_state["messages"]:
        if m.__class__.__name__ == "ToolMessage":
            try:
                parsed = json.loads(m.content)
            except Exception:
                parsed = m.content
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "id" in item:
                        seen[item["id"]] = item
    tool_results = list(seen.values())

    reply = final_state["messages"][-1].content
    count = len(tool_results)
    if tool_results:
        reply = f"Found {count} projects. " + reply
    return {"reply": reply, "tool_results": tool_results}