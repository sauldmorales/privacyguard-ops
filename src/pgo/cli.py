import typer
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()

@app.command()
def status():
    """Show current system status (stub)."""
    console.print("[green]PGO status:[/green] OK (stub)")

if __name__ == "__main__":
    app()

def main() -> None:
    app()

if __name__ == "__main__":
    main()
