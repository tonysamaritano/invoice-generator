#!/usr/bin/env python3
"""
Invoice Generator - Generates HTML and PDF invoices from YAML data
"""

import yaml
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from validate_invoice import validate_invoice_file
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint


OUTPUT_DIR = Path("output")
console = Console()


def load_yaml_data(yaml_path):
    """Load and parse YAML invoice data"""
    with open(yaml_path, 'r') as file:
        data = yaml.safe_load(file)
    return data


def calculate_totals(invoice_data):
    """Calculate invoice totals"""
    items = invoice_data['invoice']['items']
    subtotal = sum(item['quantity'] * item['unit_cost'] for item in items)
    total = subtotal

    return {
        'subtotal': subtotal,
        'total': total
    }


def ensure_output_dir():
    """Ensure output directory exists"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_html(data, output_path, template_path='invoice_template.html'):
    """Generate HTML invoice from data"""
    # Calculate totals
    totals = calculate_totals(data)

    # Convert relative attachment paths to absolute file:// URIs
    for item in data['invoice']['items']:
        if 'attachments' in item:
            item['attachments'] = [
                Path(att).absolute().as_uri() if not att.startswith(('http://', 'https://', 'file://')) else att
                for att in item['attachments']
            ]

    # Setup Jinja2 environment
    template_dir = Path(template_path).parent
    template_name = Path(template_path).name
    env = Environment(loader=FileSystemLoader(template_dir if str(template_dir) != '.' else '.'))
    template = env.get_template(template_name)

    # Render template
    html_content = template.render(
        invoice=data['invoice'],
        subtotal=totals['subtotal'],
        total=totals['total']
    )

    # Write HTML file
    with open(output_path, 'w') as file:
        file.write(html_content)

    return output_path


def generate_pdf(html_path, output_path):
    """Generate PDF from HTML invoice"""
    # Images use absolute file:// URIs, so no base_url needed
    HTML(html_path).write_pdf(output_path)
    return output_path


def get_output_name(data):
    """Extract output name from invoice data"""
    invoice_id = data['invoice']['invoice_id']
    # Convert INV-2025-001 to 2025-001
    return invoice_id.lower()


def main():
    """Main function to generate invoice"""
    # Print header
    console.print("\n[bold cyan]━━━ Invoice Generator ━━━[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/yellow] python generate_invoice.py <yaml_file>")
        console.print("[dim]Example: python generate_invoice.py data/invoice_austin_fc.yaml[/dim]")
        sys.exit(1)

    yaml_path = sys.argv[1]

    # Check if YAML file exists
    if not Path(yaml_path).exists():
        console.print(f"[red]✗ Error:[/red] YAML file not found: {yaml_path}")
        sys.exit(1)

    # Create progress spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # Validate invoice YAML
        task = progress.add_task("[cyan]Validating invoice YAML...", total=None)
        is_valid, message = validate_invoice_file(yaml_path)
        progress.remove_task(task)

        if not is_valid:
            console.print(f"[red]✗ Validation failed:[/red] {message}")
            sys.exit(1)
        console.print(f"[green]✓[/green] {message}")

        # Load data and extract output name
        task = progress.add_task("[cyan]Loading invoice data...", total=None)
        data = load_yaml_data(yaml_path)
        output_name = get_output_name(data)
        progress.remove_task(task)
        console.print(f"[green]✓[/green] Invoice data loaded: [bold]{data['invoice']['invoice_id']}[/bold]")

        # Ensure output directory exists
        ensure_output_dir()

        # Generate output paths
        html_output = OUTPUT_DIR / f"{output_name}.html"
        pdf_output = OUTPUT_DIR / f"{output_name}.pdf"

        # Generate HTML
        task = progress.add_task("[cyan]Generating HTML invoice...", total=None)
        generate_html(data, html_output)
        progress.remove_task(task)
        console.print(f"[green]✓[/green] HTML invoice generated")

        # Generate PDF
        task = progress.add_task("[cyan]Generating PDF invoice...", total=None)
        generate_pdf(html_output, pdf_output)
        progress.remove_task(task)
        console.print(f"[green]✓[/green] PDF invoice generated")

    # Create summary table
    console.print()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan", justify="right")
    table.add_column(style="white")

    table.add_row("Invoice ID:", f"[bold]{data['invoice']['invoice_id']}[/bold]")
    table.add_row("Total:", f"[bold green]{data['invoice']['currency']} {calculate_totals(data)['total']:.2f}[/bold green]")
    table.add_row("HTML:", f"[link=file://{html_output.absolute()}]{html_output}[/link]")
    table.add_row("PDF:", f"[link=file://{pdf_output.absolute()}]{pdf_output}[/link]")

    panel = Panel(
        table,
        title="[bold green]✓ Invoice Generated Successfully[/bold green]",
        border_style="green",
        padding=(1, 2)
    )
    console.print(panel)
    console.print()


if __name__ == "__main__":
    main()
