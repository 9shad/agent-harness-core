import logging
from typing import Dict, Type, List
from skills.base_skill import BaseSkill

logger = logging.getLogger("agent-harness")

class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Type[BaseSkill]] = {}

    def register(self, name: str, skill_class: Type[BaseSkill]):
        self._skills[name] = skill_class
        logger.debug(f"Registered skill: {name}")

    def get_skill(self, name: str, agent) -> Optional[BaseSkill]:
        skill_class = self._skills.get(name)
        if skill_class:
            return skill_class(agent)
        return None

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

# Global skill registry
skill_registry = SkillRegistry()
