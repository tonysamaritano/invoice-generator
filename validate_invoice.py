#!/usr/bin/env python3
"""
Invoice YAML Validator - Validates invoice YAML structure and data
"""

from datetime import datetime
from pathlib import Path


class InvoiceValidationError(Exception):
    """Custom exception for invoice validation errors"""
    pass


def validate_date(date_value, field_name):
    """Validate date format (YYYY-MM-DD or date object)"""
    from datetime import date

    # Accept date objects from YAML parser
    if isinstance(date_value, date):
        return

    # Accept string dates
    if isinstance(date_value, str):
        try:
            datetime.strptime(date_value, '%Y-%m-%d')
            return
        except ValueError:
            raise InvoiceValidationError(
                f"{field_name}: Invalid date format '{date_value}'. Expected YYYY-MM-DD"
            )

    raise InvoiceValidationError(
        f"{field_name}: Must be a date string (YYYY-MM-DD) or date object"
    )


def validate_date_range(date_range, field_name):
    """Validate date or date range"""
    from datetime import date

    if isinstance(date_range, (str, date)):
        # Single date (string or date object)
        validate_date(date_range, field_name)
    elif isinstance(date_range, dict):
        # Date range
        if 'start' not in date_range or 'end' not in date_range:
            raise InvoiceValidationError(
                f"{field_name}: Date range must have 'start' and 'end' keys"
            )
        validate_date(date_range['start'], f"{field_name}.start")
        validate_date(date_range['end'], f"{field_name}.end")
    else:
        raise InvoiceValidationError(
            f"{field_name}: Must be a date string (YYYY-MM-DD), date object, or date range object with 'start' and 'end'"
        )


def validate_address(address, field_name):
    """Validate address structure"""
    required_fields = ['street', 'city', 'state', 'zip', 'country']
    for field in required_fields:
        if field not in address:
            raise InvoiceValidationError(
                f"{field_name}: Missing required field '{field}'"
            )

        # Zip can be string or int
        if field == 'zip':
            if not isinstance(address[field], (str, int)):
                raise InvoiceValidationError(
                    f"{field_name}.{field}: Must be a string or integer"
                )
            # If it's a string, ensure it's not empty
            if isinstance(address[field], str) and not address[field].strip():
                raise InvoiceValidationError(
                    f"{field_name}.{field}: Must be a non-empty string"
                )
        else:
            # Other fields must be non-empty strings
            if not isinstance(address[field], str) or not address[field].strip():
                raise InvoiceValidationError(
                    f"{field_name}.{field}: Must be a non-empty string"
                )


def validate_party(party, field_name):
    """Validate sender or bill_to party"""
    if 'organization' not in party:
        raise InvoiceValidationError(
            f"{field_name}: Missing required field 'organization'"
        )

    if 'address' not in party:
        raise InvoiceValidationError(
            f"{field_name}: Missing required field 'address'"
        )

    validate_address(party['address'], f"{field_name}.address")


def validate_items(items):
    """Validate invoice items"""
    if not isinstance(items, list) or len(items) == 0:
        raise InvoiceValidationError(
            "invoice.items: Must be a non-empty list"
        )

    for i, item in enumerate(items):
        item_name = f"invoice.items[{i}]"

        # Required fields
        required_fields = {
            'description': str,
            'units': str,
            'quantity': (int, float),
            'unit_cost': (int, float)
        }

        for field, expected_type in required_fields.items():
            if field not in item:
                raise InvoiceValidationError(
                    f"{item_name}: Missing required field '{field}'"
                )
            if not isinstance(item[field], expected_type):
                type_name = expected_type.__name__ if not isinstance(expected_type, tuple) else ' or '.join(t.__name__ for t in expected_type)
                raise InvoiceValidationError(
                    f"{item_name}.{field}: Must be of type {type_name}"
                )

        # Validate quantity and unit_cost are positive
        if item['quantity'] <= 0:
            raise InvoiceValidationError(
                f"{item_name}.quantity: Must be greater than 0"
            )
        if item['unit_cost'] < 0:
            raise InvoiceValidationError(
                f"{item_name}.unit_cost: Must be non-negative"
            )

        # Validate date or date_range
        if 'date' in item:
            validate_date_range(item['date'], f"{item_name}.date")

        # Validate attachments (optional, must be list if present)
        if 'attachments' in item:
            if not isinstance(item['attachments'], list):
                raise InvoiceValidationError(
                    f"{item_name}.attachments: Must be a list of file paths"
                )
            for j, attachment in enumerate(item['attachments']):
                if not isinstance(attachment, str):
                    raise InvoiceValidationError(
                        f"{item_name}.attachments[{j}]: Must be a string (file path)"
                    )


def validate_invoice(data):
    """Validate complete invoice structure"""
    from datetime import date

    if 'invoice' not in data:
        raise InvoiceValidationError("Missing root 'invoice' key")

    invoice = data['invoice']

    # Required top-level fields (excluding date fields which can be date objects)
    required_fields = {
        'invoice_id': str,
        'currency': str,
        'sender': dict,
        'bill_to': dict,
        'items': list
    }

    for field, expected_type in required_fields.items():
        if field not in invoice:
            raise InvoiceValidationError(
                f"invoice: Missing required field '{field}'"
            )
        if not isinstance(invoice[field], expected_type):
            raise InvoiceValidationError(
                f"invoice.{field}: Must be of type {expected_type.__name__}"
            )

    # Check date fields exist
    for date_field in ['date', 'due_date']:
        if date_field not in invoice:
            raise InvoiceValidationError(
                f"invoice: Missing required field '{date_field}'"
            )

    # Validate dates
    validate_date(invoice['date'], 'invoice.date')
    validate_date(invoice['due_date'], 'invoice.due_date')

    # Validate parties
    validate_party(invoice['sender'], 'invoice.sender')
    validate_party(invoice['bill_to'], 'invoice.bill_to')

    # Validate items
    validate_items(invoice['items'])

    # Validate optional status field
    if 'status' in invoice:
        valid_statuses = ['draft', 'final', 'paid', 'overdue']
        if invoice['status'] not in valid_statuses:
            raise InvoiceValidationError(
                f"invoice.status: Must be one of {valid_statuses}"
            )

    return True


def validate_invoice_file(yaml_path):
    """Validate invoice YAML file and return helpful error messages"""
    import yaml

    try:
        with open(yaml_path, 'r') as file:
            data = yaml.safe_load(file)

        validate_invoice(data)
        return True, "Invoice YAML is valid!"

    except yaml.YAMLError as e:
        return False, f"YAML parsing error: {str(e)}"
    except InvoiceValidationError as e:
        return False, f"Validation error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    console.print("\n[bold cyan]━━━ Invoice YAML Validator ━━━[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/yellow] python validate_invoice.py <yaml_file>")
        sys.exit(1)

    yaml_path = sys.argv[1]

    if not Path(yaml_path).exists():
        console.print(f"[red]✗ Error:[/red] File not found: {yaml_path}")
        sys.exit(1)

    is_valid, message = validate_invoice_file(yaml_path)

    if is_valid:
        panel = Panel(
            f"[green]{message}[/green]",
            title="[bold green]✓ Validation Passed[/bold green]",
            border_style="green"
        )
        console.print(panel)
        console.print()
        sys.exit(0)
    else:
        panel = Panel(
            f"[red]{message}[/red]",
            title="[bold red]✗ Validation Failed[/bold red]",
            border_style="red"
        )
        console.print(panel)
        console.print()
        sys.exit(1)
