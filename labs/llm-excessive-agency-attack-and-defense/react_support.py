import json
import re
from typing import Union

from langchain_core._api import suppress_langchain_beta_warning
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.load.load import loads
from langsmith import Client

from langchain.agents.output_parsers.react_single_input import (
    ReActSingleInputOutputParser,
)

_ACTION_RE = re.compile(
    r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)",
    re.DOTALL,
)
_NEXT_BLOCK_RE = re.compile(r"\n(?:Thought|Final Answer|Observation)\s*:")


def pull_react_prompt():
    """Load hwchase17/react and pass an explicit deserialization allowlist.

    LangSmith's hub.pull() calls loads() without allowed_objects, which warns
    that the default allowlist is about to change.
    """
    commit = Client().pull_prompt_commit("hwchase17/react")
    with suppress_langchain_beta_warning():
        return loads(json.dumps(commit.manifest))


class LabReActOutputParser(ReActSingleInputOutputParser):
    """Accept the tool call or the report when the model mixes the two.

    The stock parser errors if a message contains both an Action and a Final
    Answer, and it also errors when the report is written without an Action line.
    Those errors are fed back to the model and the same report is generated again.
    """

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        action_match = _ACTION_RE.search(text)
        if action_match and "Final Answer:" not in text[: action_match.start()]:
            action = action_match.group(1).strip().split("\n")[0].strip()
            action_input = _NEXT_BLOCK_RE.split(action_match.group(2), maxsplit=1)[0]
            action_input = action_input.strip().strip('"')
            if action and action_input:
                return AgentAction(action, action_input, text)

        if "Final Answer:" in text:
            return AgentFinish(
                {"output": text.split("Final Answer:")[-1].strip()},
                text,
            )

        stripped = text.strip()
        if len(stripped) > 200 and _ACTION_RE.search(stripped) is None:
            return AgentFinish({"output": stripped}, text)

        return super().parse(text)
