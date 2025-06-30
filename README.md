# Agentic Researcher

An advanced AI research assistant built using OpenAI Swarm framework that can understand research queries, gather information from the web, validate answers, and store knowledge for future reference.

## Features

- 🤖 **Multi-Agent Architecture**: Uses OpenAI Swarm for intelligent agent coordination
- 🔍 **Web Research**: DuckDuckGo search with Playwright web scraping
- 🧠 **Knowledge Base**: Local Qdrant vector database for storing and retrieving information
- ✅ **Answer Validation**: Review/Reflection agent ensures answer quality before delivery
- 💻 **Code Execution**: Terminal runner for executing generated code
- 🗄️ **Data Persistence**: SQLite database for project management and logs
- 🔧 **Azure OpenAI**: GPT-4o integration via Azure OpenAI

## Architecture

The system consists of several specialized agents:

1. **Planner Agent**: Breaks down research queries into actionable steps
2. **Researcher Agent**: Performs web searches and information gathering
3. **Coder Agent**: Generates code when needed
4. **Review Agent**: Validates and refines answers before delivery
5. **Runner Agent**: Executes generated code in a safe environment

## Requirements

- Python 3.10+
- Azure OpenAI API key
- Qdrant (local installation)
- Playwright browsers

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```bash
   playwright install --with-deps
   ```
4. Set up your configuration in `config.toml`

## Usage

```bash
python main.py
```

## Configuration

Create a `config.toml` file with your Azure OpenAI settings:

```toml
[azure_openai]
api_key = "your-azure-openai-api-key"
endpoint = "https://your-resource.openai.azure.com/"
api_version = "2024-02-15-preview"
deployment_name = "gpt-4o"

[qdrant]
host = "localhost"
port = 6333
collection_name = "research_knowledge"

[database]
path = "data/research.db"
```

## Project Structure

```
agentic-researcher/
├── src/
│   ├── agents/
│   │   ├── planner.py
│   │   ├── researcher.py
│   │   ├── coder.py
│   │   ├── reviewer.py
│   │   └── runner.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── knowledge_base.py
│   ├── services/
│   │   ├── web_search.py
│   │   ├── code_executor.py
│   │   └── azure_client.py
│   └── utils/
│       ├── logger.py
│       └── helpers.py
├── data/
├── logs/
├── temp/
├── main.py
├── requirements.txt
└── config.toml
```

## Web Search Pipeline

Agentres uses a robust, multi-fallback web search pipeline:

1. **DuckDuckGo Search** (primary)
2. **Tavily API** (secondary, requires `TAVILY_API_KEY` in `.env`)
3. **Google Custom Search API** (tertiary, requires `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` in `.env`)

For each research sub-query:
- The query is sanitized to remove code block markers, brackets, and extraneous punctuation, and to ensure only meaningful queries are sent to search.
- Up to 5 ranked URLs are retrieved (no snippets).
- The system attempts to scrape the first URL; if it fails, it tries the next, and so on.
- Only if all scraping fails for all URLs does it fall back to using search snippets.

### Configuration
- All search settings (max_results, timeout, API keys) are managed in `config.yaml` and `.env`. 