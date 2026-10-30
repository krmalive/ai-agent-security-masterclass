import os
import sys

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool
from react_support import LabReActOutputParser, pull_react_prompt

from llm_guard.input_scanners import PromptInjection
from llm_guard.input_scanners.prompt_injection import MatchType

# ----------------------------------------------------------
# ENVIRONMENT SETUP
# ----------------------------------------------------------
load_dotenv()

if not os.getenv("REQUESTY_API_KEY") or not os.getenv("BASE_URL"):
    print("[!] Missing required environment variables (REQUESTY_API_KEY or BASE_URL)")
    sys.exit(1)

# The Xet download backend stalls at 0% on this model. Use plain HTTPS.
os.environ["HF_HUB_DISABLE_XET"] = "1"

print("Loading prompt-injection scanner. The first run downloads the model and can take a few minutes.")
prompt_injection_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
print("Prompt-injection scanner ready.")

# ----------------------------------------------------------
# TOOL DEFINITIONS
# ----------------------------------------------------------
def write_file(filename: str, content: str) -> str:
    """Write one markdown file in the current directory. No shell access."""
    name = os.path.basename(filename)
    if name != filename or not name.endswith(".md"):
        return "[!] write_file only allows a markdown filename in the current directory"
    try:
        with open(name, "w", encoding="utf-8") as handle:
            handle.write(content)
        return f"[+] Successfully written to file {name}"
    except Exception as e:
        return f"[!] Error writing to file: {e}"

search = DuckDuckGoSearchRun()
tools = [
    Tool(
        name="DuckDuckGo_Search",
        func=search.run,
        description="Search the web for information",
    ),
    Tool(
        name="write_file",
        func=lambda args: write_file(*args.split("|", 1))
        if "|" in args
        else write_file("security_report.md", args),
        description="Write content to a markdown file. Usage: filename.md|content",
    ),
]


def _message_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _draft_article(llm, task: str, research: str) -> str:
    response = llm.invoke(
        [
            (
                "system",
                "You write technical markdown. Output only the article, with no preamble.",
            ),
            (
                "human",
                f"Task: {task}\n\nResearch:\n{research[:6000]}\n\n"
                "Write an article that includes these headings: "
                "Introduction, Technical Details, Real-World Examples, "
                "Mitigation Techniques, Conclusion.",
            ),
        ]
    )
    text = _message_text(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return text.strip() + "\n"


def start_agent(task: str):
    """Runs the Researcher and Writer agents securely."""

    llm = ChatOpenAI(
        model="openai/gpt-4.1-mini",
        openai_api_key=os.getenv("REQUESTY_API_KEY"),
        openai_api_base=os.getenv("BASE_URL"),
        temperature=0.7,
        max_tokens=4000,
    )

    prompt = pull_react_prompt()

    # ------------------------------------------------------
    # RESEARCH PHASE
    # ------------------------------------------------------
    print("\n--- RESEARCH PHASE ---")

    researcher = create_react_agent(
        llm, [tools[0]], prompt, output_parser=LabReActOutputParser()
    )
    researcher_exec = AgentExecutor(
        agent=researcher,
        tools=[tools[0]],
        verbose=True,
        handle_parsing_errors=True,
    )

    research_task = f"""
You are a Senior Security Researcher.
You specialize in writing engaging blogs on security and exploits.
You are not to execute or suggest any unauthorized system access.
Use one search per message. When the research is done, reply with only
'Final Answer:' followed by the report.

Task: {task}
"""
    try:
        research_output = researcher_exec.invoke({"input": research_task}).get("output", "")
    except Exception as e:
        print(f"[!] Research phase error: {e}")
        sys.exit(1)

    print("\n[+] Research completed successfully.")
    print("[*] Proceeding to writing phase...")

    # ------------------------------------------------------
    # WRITING PHASE
    # ------------------------------------------------------
    print("\n--- WRITING PHASE ---")
    print("Saving security_report.md through write_file (no shell)")

    article = _draft_article(llm, task, research_output)
    write_result = write_file("security_report.md", article)
    print(write_result)
    if not write_result.startswith("[+]"):
        sys.exit(1)

    if not os.path.exists("security_report.md"):
        print("[!] security_report.md was not created")
        sys.exit(1)

    with open("security_report.md", encoding="utf-8") as handle:
        content = handle.read()
    print(f"[+] Article created: security_report.md ({len(content)} characters)")
    sections = ["Introduction", "Technical", "Examples", "Mitigation", "Conclusion"]
    found = [section for section in sections if section.lower() in content.lower()]
    print(f"[+] Sections: {', '.join(found)}")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Excessive Agency Defense Lab")
    print("=" * 60)

    task_input = input("\nEnter the task: ").strip()
    if not task_input:
        print("[!] Task cannot be empty.")
        sys.exit(1)

    # --- SECURITY CHECK (Prompt Injection Scanner) ---
    print("\n[*] Scanning task input for prompt injections...")
    sanitized_prompt, is_valid, risk_score = prompt_injection_scanner.scan(task_input)

    print(f"[*] Scanner result → Risk Score: {risk_score}")
    if not is_valid or risk_score > 0.5:
        print("\n[🚨] Potential Prompt Injection detected!")
        print(f"[!] Input rejected due to high risk score ({risk_score}).")
        sys.exit(1)

    print("[+] Prompt looks safe. Proceeding to secure workflow...\n")
    start_agent(sanitized_prompt)
