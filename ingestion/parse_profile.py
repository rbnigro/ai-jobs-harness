import os
from pypdf import PdfReader


KNOWN_TECHNOLOGIES = (
    "Python", "SQL", "Java", "JavaScript", "TypeScript", "AWS", "Azure",
    "GCP", "Docker", "Git", "Machine Learning", "Deep Learning", "Angular",
    "LLM", "LLMs", "RAG", "Power BI", "Excel",
)
KNOWN_ROLES = (
    "Engenheiro de IA", "AI Engineer", "Data Engineer", "Machine Learning Engineer",
    "Data Scientist", "Analista de Dados", "Dev SR", "Software Engineer",
)

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
            skills_detectadas = ["Resolução de Problemas", "Gestão de Projetos"]

        cargos_detectados = [role for role in KNOWN_ROLES if role.lower() in raw_text.lower()]
        if not cargos_detectados:
            cargos_detectados = [objetivo]

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
