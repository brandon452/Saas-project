from datetime import date


def csv_filename(resource: str) -> str:
    today = date.today().isoformat()
    return f"{resource}-{today}.csv"


def pdf_filename(resource: str, identifier: str) -> str:
    return f"{resource}-{identifier}.pdf"
