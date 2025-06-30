import sys
import os
import logging
import json
from datetime import datetime
from swarm import Swarm
from src.core.agent_registry import AGENTS
from src.core.config import Config
from src.core.database import Database
from src.core.knowledge_base import KnowledgeBase
from src.services.azure_client import AzureOpenAIClient
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.text import Text
from src.agents.mother import MotherAgent
from rich.syntax import Syntax
import re

console = Console()

# Set up logging configuration
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"agentres_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("agentres")

# Helper to print colored agent output
COLOR_MAP = {
    "cyan": "bold cyan",
    "yellow": "bold yellow",
    "magenta": "bold magenta",
    "green": "bold green",
    "blue": "bold blue",
    "red": "bold red",
    "white": "bold white",
    "bright_blue": "bold bright_blue",
    "bright_magenta": "bold bright_magenta",
    "bright_yellow": "bold bright_yellow",
    "grey50": "grey50",
}

def print_agent_section(agent, output, color, context=None):
    style = COLOR_MAP.get(color, "bold white")
    console.rule(f"[{style}]{agent}")
    # Special handling for Planner
    if agent.lower() == "planner" and isinstance(output, (dict, list, str)):
        # Print plan as readable steps
        if isinstance(output, list):
            console.print("[bold magenta]Plan:[/bold magenta]")
            for idx, step in enumerate(output, 1):
                if isinstance(step, dict):
                    console.print(f"[bold cyan]Step {idx}:[/bold cyan] [yellow]{step.get('task', '')}[/yellow]")
                    console.print(f"  [green]Agent:[/green] {step.get('agent', '')}")
                    console.print(f"  [blue]Reasoning:[/blue] {step.get('reasoning', '')}\n")
        elif isinstance(output, str):
            console.print(Markdown(output), style=style)
        else:
            console.print(str(output), style=style)
        return
    # Special handling for Researcher
    if agent.lower() == "researcher" and context and 'research_details' in context:
        details = context['research_details']
        for detail in details:
            console.print(f"[bold cyan]Sub-query:[/bold cyan] {detail['query']}")
            if detail['ranked_urls']:
                console.print("[bold]Ranked URLs:[/bold]")
                for idx, url in enumerate(detail['ranked_urls'], 1):
                    console.print(f"  {idx}. {url}")
            if detail['char_counts']:
                console.print("[bold]Characters scraped from each URL:[/bold]")
                for cc in detail['char_counts']:
                    console.print(f"  {cc['url']}: {cc['chars']} chars")
            console.print("[bold]---[/bold]")
        return
    # Special handling for Formatter
    if agent.lower() == "formatter":
        console.print("[bold green]Formatter has cleaned and prepared the scraped data for synthesis.[/bold green]")
        return
    # Special handling for Answer
    if agent.lower() == "answer":
        # Print as a single, long, well-structured output
        if isinstance(output, str):
            console.print(Markdown(output), style=style)
        else:
            console.print(str(output), style=style)
        return
    # Default: previous logic
    if isinstance(output, str):
        code_block_pattern = r'```(\w+)?\n([\s\S]*?)```'
        last_end = 0
        for match in re.finditer(code_block_pattern, output):
            start, end = match.span()
            if start > last_end:
                text_part = output[last_end:start].strip()
                if text_part:
                    header_lines = []
                    for line in text_part.split('\n'):
                        if line.strip().startswith('#'):
                            header_level = line.count('#', 0, line.find(' '))
                            header_style = f"bold magenta" if header_level == 1 else ("bold cyan" if header_level == 2 else "bold yellow")
                            console.print(Text(line.strip(), style=header_style))
                        else:
                            console.print(Markdown(line), style=style)
            lang = match.group(1) or "python"
            code = match.group(2)
            syntax = Syntax(code, lang, theme="monokai", line_numbers=False, word_wrap=True)
            console.print(Panel(syntax, title=f"[bold]{lang.capitalize()} Code[/bold]", border_style="bright_blue"))
            last_end = end
        if last_end < len(output):
            text_part = output[last_end:].strip()
            if text_part:
                header_lines = []
                for line in text_part.split('\n'):
                    if line.strip().startswith('#'):
                        header_level = line.count('#', 0, line.find(' '))
                        header_style = f"bold magenta" if header_level == 1 else ("bold cyan" if header_level == 2 else "bold yellow")
                        console.print(Text(line.strip(), style=header_style))
                    else:
                        console.print(Markdown(line), style=style)
    else:
        console.print(Panel(str(output), style=style))

def get_session_name_from_llm(query):
    # For now, just use a simple transformation; in production, use LLM
    name = query.strip().replace(' ', '_').replace('?', '').replace('.', '').lower()
    return name[:40] + ("_session" if len(name) < 30 else "")

def save_session_json(session_name, history):
    os.makedirs("sessions", exist_ok=True)
    session_file = os.path.join("sessions", f"{session_name}.json")
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    logger.info(f"Session saved to {session_file}")

def main():
    console.print("[bold cyan]Welcome to Agentres, an Agentic Researcher![/bold cyan]")
    mother = MotherAgent()
    context = None
    history = []
    session_name = None
    while True:
        if not context:
            user_query = Prompt.ask("[bold yellow]Enter your research question[/bold yellow]")
            if not user_query:
                console.print("[red]No query provided. Exiting.[/red]")
                sys.exit(0)
            session_id = datetime.now().strftime('%Y%m%d%H%M%S')
            session_name = get_session_name_from_llm(user_query)
            context = {"session_id": session_id}
            context, new_history = mother.run(user_query, context)
            for step in new_history:
                print_agent_section(step["agent"], step["output"], step["color"], context)
                history.append(step)
            save_session_json(session_name, history)
        else:
            user_input = Prompt.ask("[bold yellow]What would you like to do next? (type anything, e.g. 'run the code', 'show sources', 'exit')[/bold yellow]")
            logger.info(f"User input: {user_input}")
            input_lower = user_input.lower()
            if any(word in input_lower for word in ["exit", "quit", "bye"]):
                console.print("[bold green]\n[✓] Session complete! Goodbye.[/bold green]")
                save_session_json(session_name, history)
                break
            else:
                # Always treat as a natural language follow-up command
                context['is_followup'] = True
                context, new_history = mother.run(user_input, context)
                for step in new_history:
                    print_agent_section(step["agent"], step["output"], step["color"], context)
                    history.append(step)
                save_session_json(session_name, history)
                continue

if __name__ == "__main__":
    main() 