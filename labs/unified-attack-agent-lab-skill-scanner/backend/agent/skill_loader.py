from pathlib import Path
from typing import Dict


class SkillLoader:
    def __init__(self, skills_root: str = "/app/skills") -> None:
        self.skills_root = Path(skills_root)

    def load_all(self) -> Dict[str, str]:
        loaded: Dict[str, str] = {}
        if not self.skills_root.exists():
            return loaded
        for skill_file in self.skills_root.glob("*/SKILL.md"):
            skill_name = skill_file.parent.name
            loaded[skill_name] = skill_file.read_text(encoding="utf-8")
        return loaded
