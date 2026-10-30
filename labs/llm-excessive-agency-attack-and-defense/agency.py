import base64
import os
import sys
from langchain_community.tools import DuckDuckGoSearchRun, ShellTool
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from dotenv import load_dotenv

from react_support import LabReActOutputParser, pull_react_prompt

load_dotenv()

# Initialize API
requesty_api_key = os.getenv("REQUESTY_API_KEY")
BASE_URL = os.getenv("BASE_URL")

# Create LLM
llm = ChatOpenAI(
    model="openai/gpt-4.1-mini",
    openai_api_key=requesty_api_key,
    openai_api_base=BASE_URL,
    temperature=0.7,
    max_tokens=4000
)

search = DuckDuckGoSearchRun()
shell = ShellTool()

tools = [
    Tool(
        name="DuckDuckGo_Search",
        func=search.run,
        description="Search the internet for up-to-date vulnerability information, CVEs, and exploit details."
    ),
    Tool(
        name="Shell_Command",
        func=shell.run,
        description="Execute shell commands to gather system information"
    )
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


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
    return stripped.strip() + "\n"


def draft_article(task: str, research: str) -> str:
    """Draft markdown outside the ReAct loop.

    The hwchase17/react parser treats the words Action, Thought, and Final Answer
    as control tokens. A full article in that loop is parsed as a broken tool call
    and the file is never written.
    """
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
    return _strip_fence(_message_text(response))


def save_with_shell(content: str) -> str:
    """Write the article by executing a shell command. This is the vulnerable write path."""
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    command = (
        f"{sys.executable} -c \"import base64; "
        f"open('security_report.md','wb').write(base64.b64decode('{encoded}'))\""
    )
    print("Saving security_report.md through Shell_Command")
    result = shell.run(command)
    return result if isinstance(result, str) else str(result)


def start_agent(task: str):
    prompt = pull_react_prompt()
    
    # Researcher agent setup
    researcher_prompt = """You are a Senior Security Researcher.
You specialize in real-world attack scenarios and exploits against popular software.
Your goal is to research and provide detailed information on security vulnerabilities.

When researching:
1. Search for relevant vulnerability information
2. Gather technical details about attack vectors
3. Compile findings into a comprehensive report
4. Use the tools you have access to for proper serach on the topic user as asked for

Use one tool call per message. When the research is done, reply with only
'Final Answer:' followed by the report. Do not put an Action and a Final Answer
in the same message."""
    
    print("\n=== RESEARCH PHASE ===\n")
    
    research_agent = create_react_agent(
        llm, tools, prompt, output_parser=LabReActOutputParser()
    )
    research_executor = AgentExecutor(
        agent=research_agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=6,
        return_intermediate_steps=True
    )
    
    research_task = f"{researcher_prompt}\n\nTask: {task}\n\nProvide a detailed research report."
    
    try:
        research_result = research_executor.invoke({"input": research_task})
        research_output = research_result.get("output", "")
        
        if len(research_output) < 500:
            intermediate_steps = research_result.get("intermediate_steps", [])
            all_findings = []
            for step in intermediate_steps:
                if len(step) > 1 and isinstance(step[1], str):
                    all_findings.append(step[1])
            if all_findings:
                research_output = "\n\n".join(all_findings)
        
        print(f"\n✓ Research completed\n")
        
    except Exception as e:
        print(f"✗ Research error: {e}\n")
        research_output = "Limited research data available."
    
    print("=== WRITING PHASE ===\n")

    try:
        article = draft_article(task, research_output)
        shell_result = save_with_shell(article)
        if shell_result and shell_result.strip():
            print(shell_result.strip())
        print("\n✓ Writing completed\n")
    except Exception as e:
        print(f"✗ Writing error: {e}\n")
    
    # Verification
    print("=== VERIFICATION ===\n")
    
    if os.path.exists('security_report.md'):
        with open('security_report.md', 'r') as f:
            content = f.read()
            print(f"✓ Article created: security_report.md")
            print(f"✓ Size: {len(content)} characters")
            
            sections = ['Introduction', 'Technical', 'Examples', 'Mitigation', 'Conclusion']
            found = [s for s in sections if s.lower() in content.lower()]
            print(f"✓ Sections: {', '.join(found)}\n")
    else:
        print("✗ File not created\n")
    
    print("=== COMPLETED ===\n")

if __name__ == "__main__":
    task_input = input("Enter task: ")
    start_agent(task_input)