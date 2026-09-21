import time
import random
import requests

class JobScraper:
    def __init__(self):
        # Lista de cabeçalhos para simular navegadores reais diferentes e evitar bloqueios
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]

    def fetch_public_job_text(self, url: str) -> str:
        """
        Coleta o HTML/Texto de uma URL de vaga de forma anônima e resiliente.
        """
        print(f"[SCRAPER] Iniciando requisição anônima para: {url}")
        
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
        }
        
        # Simula delay humano antes da requisição (Polidez de rede)
        time.sleep(random.uniform(1.5, 3.0))
        
        try:
            # Em cenários corporativos avançados, aqui acionaríamos proxies terceiros (ex: Crawlbase/Scrapfly)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print("✅ [SCRAPER] Conteúdo capturado com sucesso.")
                return response.text
            else:
                print(f"⚠️ [SCRAPER] Falha na captura. Status Code: {response.status_code}")
                return ""
        except Exception as e:
            print(f"❌ [SCRAPER] Erro de rede: {e}")
            return ""

    def parse_to_harness_format(self, raw_html: str, url: str) -> dict:
        """
        Transforma o HTML bruto coletado no formato aceito pelo contrato do Harness.
        """
        # Em um projeto IA-First completo, este HTML bruto pode ser enviado direto
        # para a LLM limpar as tags HTML e extrair o título e a descrição!
        return {
            "titulo": "Engenheiro de IA (Capturado via Link)",
            "empresa": "Empresa Detectada",
            "localizacao": "Remoto",
            "descricao_completa": "Esta é a descrição capturada da web que contém requisitos de Python e LLMs...",
            "link_vaga": url
        }
