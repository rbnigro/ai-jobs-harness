import re
from pathlib import Path

from data_contracts.user_profile import UserProfile


SEARCH_PROFILE_PATH = Path(__file__).with_name("search_profile.md")


def _clean_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean_value = " ".join(value.strip().split())
        if clean_value and clean_value not in result:
            result.append(clean_value)
    return result


def recreate_search_profile(profile: UserProfile) -> Path:
    roles = _clean_values([
        *profile.cargos_busca,
        profile.titulo_atual,
        profile.objetivo_ia,
        "Engenheiro de IA",
        "AI Engineer",
    ])
    technologies = _clean_values(profile.competencias)

    SEARCH_PROFILE_PATH.unlink(missing_ok=True)
    content = "# Perfil de busca\n\n## Cargos\n"
    content += "\n".join(f"- {role}" for role in roles)
    content += "\n\n## Tecnologias\n"
    content += "\n".join(f"- {technology}" for technology in technologies)
    content += "\n"
    SEARCH_PROFILE_PATH.write_text(content, encoding="utf-8")
    return SEARCH_PROFILE_PATH


def load_search_terms(path: Path = SEARCH_PROFILE_PATH) -> tuple[list[str], list[str]]:
    section = ""
    roles: list[str] = []
    technologies: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = line.strip().lower()
        if heading == "## cargos":
            section = "roles"
        elif heading == "## tecnologias":
            section = "technologies"
        elif line.strip().startswith("-"):
            value = re.sub(r"^\s*-\s*", "", line).strip()
            if section == "roles":
                roles.append(value)
            elif section == "technologies":
                technologies.append(value)
    return _clean_values(roles), _clean_values(technologies)