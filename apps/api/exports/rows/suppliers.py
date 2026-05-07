HEADERS = [
    "code",
    "display_name",
    "legal_name",
    "email",
    "phone",
    "payment_terms_days",
    "default_lead_time_days",
    "currency",
    "country",
    "is_active",
]


def to_row(supplier):
    return [
        supplier.code,
        supplier.display_name,
        supplier.legal_name,
        supplier.email,
        supplier.phone,
        supplier.payment_terms_days if supplier.payment_terms_days is not None else "",
        supplier.default_lead_time_days if supplier.default_lead_time_days is not None else "",
        supplier.currency,
        supplier.country,
        supplier.is_active,
    ]
