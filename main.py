import typer
import rich
import json
import os
import logging
import uuid
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler
from agents.coordinator import Coordinator
from core.tool_registry import registry

app = typer.Typer()
console = Console()
logger = logging.getLogger("agent-harness")

def setup_logging(debug: bool = False, project_root: str = ".", session_id: Optional[str] = None):
    # Use a single root logger for everything
    root_logger = logging.getLogger()
    # Clear existing handlers to avoid duplicates on restart
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    # 1. Console Handler: Use RichHandler for beautiful, colorized logs
    console_handler = RichHandler(rich_tracebacks=True, markup=True)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # 2. File Handler: Show everything (DEBUG+) in a session file
    if debug:
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        log_dir = os.path.join(project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"session_{session_id}.log")

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        logger.info(f"Debug logging enabled. Session log: {log_file}")

async def main_loop(
    provider: str,
    api_key: str,
    ollama_model: str,
    ollama_url: str,
    debug: bool,
    project_root: str
):
    setup_logging(debug, project_root=project_root)

    console.print(Panel(f"[bold blue]Agent Harness Interactive Session Started[/bold blue]\nProvider: [yellow]{provider}[/yellow]"), style="blue")
    console.print("[dim]Type 'exit' or 'quit' to stop the session.[/dim]\n")

    try:
        provider_config = {}
        if provider == "anthropic":
            if not api_key:
                raise ValueError("api_key is required for anthropic provider")
            provider_config = {"api_key": api_key}
        elif provider == "ollama":
            provider_config = {"model": ollama_model, "base_url": ollama_url}

        mcp_configs = []
        mcp_config_path = os.path.join(project_root, "mcp_config.json")
        if os.path.exists(mcp_config_path):
            try:
                with open(mcp_config_path, 'r', encoding='utf-8') as f:
                    mcp_configs = json.load(f)

                # Log the number of servers found in the dict
                server_count = len(mcp_configs.get("mcpServers", {})) if isinstance(mcp_configs, dict) else 0
                logger.info(f"Loaded {server_count} MCP server configurations from {mcp_config_path}")
            except Exception as e:
                logger.error(f"Failed to load mcp_config.json: {e}")

        coordinator = Coordinator(
            provider=provider,
            provider_config=provider_config,
            project_root=project_root,
            mcp_configs=mcp_configs
        )

        await coordinator.initialize()

        try:
            while True:
                # Using rich prompt for the user input
                query = console.input("[bold green]User >> [/bold green]")

                if query.lower() in ["exit", "quit"]:
                    console.print("[yellow]Exiting session. Goodbye![/yellow]")
                    break

                if not query.strip():
                    continue

                with console.status("[bold blue]Agent is processing..."):
                    # We just call handle_request. Since the Coordinator holds
                    # the main_agent which keeps the message history, the session is preserved.
                    result = await coordinator.handle_request(query)

                console.print("\n[bold green]Agent >> [/bold green]")
                console.print(Panel(result, expand=False))
                console.print("\n")
        finally:
            await coordinator.stop()

    except Exception as e:
        console.print(f"[bold red]Error occurred:[/bold red] {e}")
        if debug:
            logging.exception("Detailed stack trace:")


@app.command()
def run(
    provider: str = typer.Option("anthropic", help="LLM provider: 'anthropic' or 'ollama'"),
    api_key: str = typer.Option(None, envvar="ANTHROPIC_API_KEY", help="Anthropic API Key"),
    ollama_model: str = typer.Option("llama3", help="Ollama model to use"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama base URL"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
    project_root: str = typer.Option(".", help="Path to the project root for memory storage")
):
    """
    Advanced Agent Harness Interactive REPL
    """
    asyncio.run(main_loop(provider, api_key, ollama_model, ollama_url, debug, project_root))

if __name__ == "__main__":
    app()
