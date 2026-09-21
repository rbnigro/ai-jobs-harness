import os
from pathlib import Path

from pypdf import PdfReader


KEYWORDS_PATH = Path(__file__).with_name("profile_keywords.md")


def _load_keywords_from_markdown(path: Path = KEYWORDS_PATH) -> tuple[list[str], list[str]]:
    """Lê as listas de tecnologias e cargos de um arquivo Markdown."""
    if not path.exists():
        return [], []

    section = None
    technologies: list[str] = []
    roles: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.lower() == "## tecnologias":
            section = "technologies"
            continue
        if line.lower() == "## cargos":
            section = "roles"
            continue
        if line.startswith("-"):
            value = line[1:].strip()
            if not value:
                continue
            if section == "technologies":
                technologies.append(value)
            elif section == "roles":
                roles.append(value)

    return technologies, roles


KNOWN_TECHNOLOGIES, KNOWN_ROLES = _load_keywords_from_markdown()

class ProfileExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_raw_text(self) -> str:
        """Lê todas as páginas do PDF do LinkedIn e extrai o texto bruto"""
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"⚠️ O arquivo PDF não foi encontrado em: {self.pdf_path}")
            
        reader = PdfReader(self.pdf_path)
        full_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
        return "\n".join(full_text)

    def mock_structure_profile(self, raw_text: str, objetivo: str) -> dict:
        """Estrutura temporariamente os dados para o Harness rodar"""
        # Procura palavras-chave comuns no texto do seu PDF para simular inteligência
        skills_detectadas = [
            technology for technology in KNOWN_TECHNOLOGIES
            if technology.lower() in raw_text.lower()
        ]
        
        # Adiciona competências padrão caso não encontre no PDF de teste
        if not skills_detectadas:
            skills_detectadas = ["Python", "SQL", "Java", "Spring Boot", "Git", "AWS"]

        cargos_detectados = [role for role in KNOWN_ROLES if role.lower() in raw_text.lower()]
        if not cargos_detectados:
            cargos_detectados = [
                "Engenheiro de IA",
                "Desenvolvedor Java",
                "Data Engineer",
                "Software Engineer",
                objetivo,
            ]

        return {
            "nome": "Usuário Identificado via PDF",
            "titulo_atual": "Profissional em Transição",
            "resumo": "Histórico lido com sucesso pelo extrator pypdf.",
            "experiencias": ["Histórico Profissional Extraído"],
            "competencias": skills_detectadas,
            "formacao": ["Educação Acadêmica"],
            "cargos_busca": cargos_detectados,
            "objetivo_ia": objetivo
        }
