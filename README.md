# AI-Driven Job Harness & Evaluation Engine 🤖💼

Este é o arcabouço corporativo e estrutural (**Harness**) projetado para engenharia de dados orientada a IA. O ecossistema ingere e analisa o perfil profissional do usuário (através do PDF exportado do LinkedIn), extrai dados de vagas em tempo real via automação web e aciona modelos fundamentais de linguagem para avaliar a aderência semântica bilateral, focando no objetivo de transição de carreira para Inteligência Artificial.

A arquitetura adota uma filosofia **IA First**, isolando a validação de contratos, resiliência de dados e observabilidade cognitiva antes do processamento ou consumo de dados externos.

---

## 🏗️ Estrutura Arquitetural do Projeto

O projeto segue um padrão de desacoplamento completo, dividindo-se em módulos especializados de Ingestão, Extração de Rede, Validação de Contratos e Inteligência Analítica:

```text
ai-jobs-harness/
├── .env                 # ARQUIVO LOCAL: Armazena chaves privadas (Ignorado no Git)
├── .venv/               # Ambiente virtual Python isolado
├── README.md            # Documentação viva e diretrizes do ecossistema (Este arquivo)
├── main.py              # Orquestrador central e executor do pipeline
├── config/              # Configurações globais e injeção de ambiente (.env)
│   └── environment.py   # Gerenciador de segurança de credenciais e tokens
├── data_contracts/      # Esquemas Pydantic para validação estrita de dados
│   ├── job_contracts.py # Contratos das vagas (Inbound Payload e Outbound Result)
│   └── user_profile.py  # Contrato estruturado do perfil de referência do usuário
├── evaluation/          # Engine de scoring e IA analítica corporativa
│   └── engine.py        # Integração real com o Google Gemini API via SDK oficial
├── ingestion/           # Processamento e ingestão de dados do usuário
│   ├── parse_profile.py # Extrator de texto bruto de arquivos PDFs (pypdf)
│   ├── job_sources.py    # RSS, newsletters, APIs parceiras e crawler permitido
│   └── profile.pdf       # O currículo exportado do LinkedIn do usuário
└── scraper/             # Módulo de automação e coleta de dados da web
    └── job_scraper.py   # Capturador de páginas resiliente com controle de User-Agents
```

---

## 📑 Fluxo de Dados e Contratos Estritos (Data Contracts)

A integridade do pipeline é blindada por tipagem estruturada através do `pydantic`. Nenhuma chamada para a API de IA ocorre caso os dados de entrada desobedeçam as regras de contrato, blindando o sistema contra gastos desnecessários de tokens.

### 1. User Profile Contract (`UserProfile`)
Estado de referência gerado a partir do PDF do usuário, mapeando metadados, resumo, competências identificadas e o objetivo estratégico de transição.

### 2. Inbound Job Contract (`JobRawPayload`)
Garante a consistência do dado bruto vindo do módulo `scraper/`, exigindo título, empresa, link e descrição completa da vaga.

### 3. Outbound Evaluation Contract (`JobEvaluationResult`)
Força a API do Gemini a consolidar sua análise em formato JSON rígido através da funcionalidade de **Structured Outputs**, respondendo nativamente com:
* **score_aderencia:** Float determinístico entre `0.0` e `1.0`.
* **justificativa:** Texto explicativo correlacionando o perfil lido e a vaga.
* **competencias_faltantes:** Lista exata de habilidades que o usuário precisa desenvolver para aquela vaga.
* **proximos_passos_sugeridos:** Estratégia recomendada para a candidatura.

---

## 🛠️ Instalação e Execução (Windows / PowerShell)

### 1. Configuração do Ambiente e Instalação
Ative o ambiente virtual e instale os SDKs atualizados do projeto:
```powershell
.venv\Scripts\Activate.ps1
pip install pydantic pypdf google-genai python-dotenv requests
```

### 2. Configuração de Credenciais
Copie `.env.example` para `.env` e adicione seu token de acesso:
```env
GEMINI_API_KEY=INSIRA_SEU_TOKEN_AQUI

# Fontes oficiais RSS/Atom, separadas por virgula
JOB_RSS_URLS=

# Arquivos locais .eml de newsletters, separados por virgula
JOB_NEWSLETTER_FILES=

# APIs parceiras que retornam uma lista JSON de vagas
JOB_PARTNER_API_URLS=

# O crawler exige allowlist de dominio e robots.txt permitindo o acesso
JOB_CRAWLER_ALLOWED_DOMAINS=
JOB_CRAWLER_URLS=

# APIs integradas de vagas
JOB_ENABLE_REMOTEOK=true
JOB_ENABLE_RSS=false
JOB_ENABLE_NEWSLETTER=false
JOB_ENABLE_PARTNER_API=false
JOB_ENABLE_CRAWLER=false
JOB_ENABLE_REMOTEOK=false
JOB_ENABLE_REMOTIVE=false
JOB_ENABLE_ADZUNA=true
JOB_ENABLE_JOOBLE=false
JOB_SEARCH_QUERY=Engenheiro de IA
JOB_SEARCH_LOCATION=Brasil
JOB_MAX_RESULTS=10
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
ADZUNA_COUNTRY=br
ADZUNA_PAGE=1
ADZUNA_RESULTS_PER_PAGE=50
ADZUNA_SORT_BY=relevance
ADZUNA_MAX_DAYS_OLD=
ADZUNA_DISTANCE=
ADZUNA_CATEGORY=
ADZUNA_FULL_TIME=
ADZUNA_PART_TIME=
ADZUNA_PERMANENT=
ADZUNA_CONTRACT=
JOOBLE_API_KEY=
JOOBLE_PAGE=1
```

O crawler bloqueia LinkedIn e Vagas.com, nao usa login e nao tenta contornar CAPTCHA ou bloqueios. Para cada URL configurada, o dominio precisa estar em `JOB_CRAWLER_ALLOWED_DOMAINS` e o `robots.txt` precisa permitir `AIJobsHarness/1.0`.

A cada execucao, o perfil de `ingestion/profile.pdf` recria `ingestion/search_profile.md` com arrays de cargos e tecnologias. O arquivo e apagado e recriado antes da busca e nao e versionado.

Remote OK e Remotive sao consultados por padrao. Adzuna exige `ADZUNA_APP_ID` e `ADZUNA_APP_KEY`; Jooble exige `JOOBLE_API_KEY`. As fontes sao independentes: se uma estiver indisponivel, as demais continuam sendo processadas.

### 3. Execução do Pipeline Coesivo
Para executar a esteira completa (Extração de vaga externa ➔ Parse do PDF do Usuário ➔ Avaliação Cognitiva Real via Gemini ➔ Geração do Relatório):
```powershell
python main.py
```

---

## 📉 Critérios de Validação da IA (Evaluation Framework)

O Harness calibra as decisões da LLM injetando instruções de sistema (`system_instruction`) com pesos definidos:

| Critério | Peso | Descrição |
| :--- | :---: | :--- |
| **Aderência Tecnológica** | 40% | Presença de stack de dados/IA na vaga (Python, LLMs, Machine Learning, SQL). |
| **Gap Analysis & Viabilidade** | 30% | Viabilidade de transição com base nas competências atuais do usuário versus exigidas. |
| **Alinhamento de Objetivo** | 20% | Foco na atuação desejada pelo usuário (Técnico vs. Negócios/Produto). |
| **Geografia / Modelo** | 10% | Compatibilidade com preferências de trabalho (Remoto, Híbrido, Presencial). |

---

## 🚀 Próximas Metas do Roadmap Técnico
1. **Refinamento do Scraper:** Implementar o parser automático das tags HTML de buscas públicas utilizando a própria LLM para separar metadados sem depender de seletores CSS fixos.
2. **Deduplicação de Vagas:** Estruturar a pasta `storage/` para salvar os IDs de vagas avaliadas no banco SQLite, evitando reprocessar e gastar chaves com vagas antigas.
