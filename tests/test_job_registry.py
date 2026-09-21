import tempfile
import unittest
from pathlib import Path

from ingestion.job_sources import is_brazilian_compatible, is_english_job, matches_query
from storage.job_registry import save_jobs_markdown


class SaveJobsMarkdownTests(unittest.TestCase):
    def test_save_jobs_markdown_creates_markdown_report(self):
        jobs = [
            {
                "titulo": "Senior Python Engineer",
                "empresa": "Acme",
                "localizacao": "Remote",
                "descricao_completa": "Trabalhar com Python e IA.",
                "link_vaga": "https://example.com/job/1",
            },
            {
                "titulo": "Data Analyst",
                "empresa": "Beta",
                "localizacao": "São Paulo",
                "descricao_completa": "Análise de dados e SQL.",
                "link_vaga": "https://example.com/job/2",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "jobs.md"
            save_jobs_markdown(jobs, output_path)

            content = output_path.read_text(encoding="utf-8")

            self.assertIn("# Vagas encontradas", content)
            self.assertIn("Senior Python Engineer", content)
            self.assertIn("https://example.com/job/1", content)
            self.assertIn("Data Analyst", content)

    def test_is_brazilian_compatible_rejects_foreign_locations(self):
        self.assertTrue(is_brazilian_compatible("Remote"))
        self.assertTrue(is_brazilian_compatible("São Paulo, SP"))
        self.assertTrue(is_brazilian_compatible("Brasil"))
        self.assertFalse(is_brazilian_compatible("Ireland"))
        self.assertFalse(is_brazilian_compatible("Mexico City, Mexico - Remote"))

    def test_is_english_job_rejects_english_postings(self):
        english_job = {
            "titulo": "Senior Software Engineer",
            "empresa": "Acme",
            "localizacao": "Remote",
            "descricao_completa": "We are looking for a software engineer to build scalable backend systems with Python, AWS and SQL. You will work with product teams and design resilient cloud applications.",
            "link_vaga": "https://example.com/en"
        }
        portuguese_job = {
            "titulo": "Engenheiro de Dados",
            "empresa": "Acme",
            "localizacao": "São Paulo",
            "descricao_completa": "Estamos buscando um profissional para desenvolver pipelines de dados em Python e SQL com foco em automação e análise.",
            "link_vaga": "https://example.com/br"
        }

        self.assertTrue(is_english_job(type("Job", (), english_job)()))
        self.assertFalse(is_english_job(type("Job", (), portuguese_job)()))

    def test_matches_query_allows_partial_keyword_matches(self):
        job = type(
            "Job",
            (),
            {
                "titulo": "Senior Data Engineer",
                "descricao_completa": "Trabalhamos com Python, SQL e pipelines de dados para IA.",
            },
        )()

        self.assertTrue(matches_query(job, "Data Engineer|Python|AI Engineer"))
        self.assertTrue(matches_query(job, "Machine Learning|Data Engineer"))
        self.assertFalse(matches_query(job, "React Native|NodeJS|Kubernetes"))

    def test_is_english_job_keeps_brazilian_remote_java_jobs(self):
        brazilian_remote_java_job = type(
            "Job",
            (),
            {
                "titulo": "Java Backend Engineer",
                "empresa": "Nubank",
                "localizacao": "Remote - Brazil",
                "descricao_completa": "We are looking for a Java Backend Engineer with Spring Boot, REST APIs, and SQL. This is a remote role based in Brazil.",
                "link_vaga": "https://example.com/java-remote-br",
            },
        )()

        self.assertFalse(is_english_job(brazilian_remote_java_job))


if __name__ == "__main__":
    unittest.main()
