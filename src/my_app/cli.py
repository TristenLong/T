import click
from rich import print


@click.command()
@click.option('--name', default='World', help='Who to greet.')
def main(name):
    """Simple CLI program that greets the user."""
    print(f"[bold green]Hello[/bold green], [yellow]{name}[/yellow]!")

if __name__ == '__main__':
    main()
