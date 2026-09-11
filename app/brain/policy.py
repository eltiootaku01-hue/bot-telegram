from enum import StrEnum


class Action(StrEnum):
    LOCAL = "local"
    TOOL = "tool"
    LLM = "llm"
    IGNORE = "ignore"


# The important rule: an LLM is an escalation path, not the default handler.
LLM_ESCALATION_RULE = (
    "Resolve deterministic commands, cached answers, game rules, database queries, "
    "permissions and other local work before escalating to an LLM."
)
