from __future__ import annotations

from app.config import Settings

from collections.abc import Callable

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tasks.task_output import TaskOutput
from app.crew.prompts import ANALYST_GOAL, PLAN_FORMAT, PLANNER_GOAL, REVIEWER_GOAL
from app.domain.models import ApplicationSurface, TestingPlan
from app.rag.tools import (
    EventSink,
    GrepApplicationCodeTool,
    ListApplicationFilesTool,
    ObservedPDFSearchTool,
    ReadApplicationFileTool,
    WSTGReferenceTool,
)


class SecurityPlanningCrewFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build(self, emit: EventSink) -> Crew:
        llm = LLM(
            model=self.settings.chat_model,
            # Explicit provider routing keeps Requesty's full provider/model
            # identifier on the wire. CrewAI otherwise strips "openai/" after
            # using it to infer the native provider.
            provider="openai",
            api_key=self.settings.requesty_api_key,
            base_url=self.settings.requesty_base_url,
            temperature=0.1,
            max_tokens=self.settings.max_output_tokens,
        )
        list_files = ListApplicationFilesTool(self.settings.shopfast_path, emit)
        grep_code = GrepApplicationCodeTool(self.settings.shopfast_path, emit)
        read_file = ReadApplicationFileTool(self.settings.shopfast_path, emit)
        search_wstg = ObservedPDFSearchTool(self.settings, emit)
        reference = WSTGReferenceTool(self.settings, emit)

        analyst = Agent(
            role="Application Analyst",
            goal=ANALYST_GOAL,
            backstory="You map code-backed application behavior into a testable attack surface.",
            tools=[list_files, grep_code, read_file],
            llm=llm,
            max_iter=24,
            allow_delegation=False,
            verbose=False,
        )
        planner = Agent(
            role="WSTG Test Planner",
            goal=PLANNER_GOAL,
            backstory="You specialize in tailoring OWASP testing guidance to real application constraints.",
            tools=[search_wstg, reference],
            llm=llm,
            max_iter=20,
            allow_delegation=False,
            verbose=False,
        )
        reviewer = Agent(
            role="Plan Reviewer",
            goal=REVIEWER_GOAL,
            backstory="You enforce evidence, feasibility, coverage, and safe testing boundaries.",
            tools=[reference],
            llm=llm,
            max_iter=14,
            allow_delegation=False,
            verbose=False,
        )

        def completed(agent_name: str, next_agent: str | None = None) -> Callable[[TaskOutput], None]:
            def callback(_: TaskOutput) -> None:
                emit("task_completed", f"{agent_name} completed its task", agent_name, None)
                if next_agent:
                    emit("agent_started", f"{next_agent} started", next_agent, None)

            return callback

        analysis_task = Task(
            description=(
                "Intelligently inspect relevant ShopFast behavior for objective: {objective}. Inventory once, "
                "grep for important concepts and call paths, then read only the files needed to verify findings. "
                "Extract the schedule and engagement constraints from the objective; do not substitute a default "
                "duration or budget. No source access is available during test execution, and source is available "
                "now solely to build the lab plan."
            ),
            expected_output="A structured, code-backed application surface model.",
            agent=analyst,
            output_pydantic=ApplicationSurface,
            callback=completed("Application Analyst", "WSTG Test Planner"),
        )
        planning_task = Task(
            description=(
                "Using the application surface from the prior task, investigate WSTG v4.2 and draft a plan that "
                "follows this user objective exactly: {objective}. The objective controls duration, time budget, "
                "scope, priorities, exclusions, and other constraints. WSTG v4.2 remains the sole guidance source. "
                f"{PLAN_FORMAT} Show judgment by recording materially plausible candidates that you reject."
            ),
            expected_output="A structured objective-aligned plan with verified WSTG references.",
            agent=planner,
            context=[analysis_task],
            output_pydantic=TestingPlan,
            callback=completed("WSTG Test Planner", "Plan Reviewer"),
        )
        review_task = Task(
            description=(
                "Audit the preceding plan against the application surface and this exact objective: {objective}. "
                "Re-verify citations, correct coverage, constraint, or scheduling issues, and return the final "
                "plan. Do not add any unverified test and do not restore any default three-day schedule."
            ),
            expected_output="The final validated TestingPlan object, ready for the lab UI.",
            agent=reviewer,
            context=[analysis_task, planning_task],
            output_pydantic=TestingPlan,
            callback=completed("Plan Reviewer"),
        )

        return Crew(
            agents=[analyst, planner, reviewer],
            tasks=[analysis_task, planning_task, review_task],
            process=Process.sequential,
            memory=False,
            cache=False,
            verbose=False,
        )
