STATUS_CONFIRMED = "confirmed:good"
STATUS_EXCEPTION = "exception:warning"
STATUSES = [STATUS_CONFIRMED, STATUS_EXCEPTION]

TITLE_COLUMN_CANDIDATES = [
    "supplier", "vendor", "payee", "vendor_payee_name", "name", "entity",
    "customer", "client", "description", "memo_description", "raw_description",
    "product", "company", "counterparty"
]
AMOUNT_COLUMN_CANDIDATES = [
    "price", "amount", "amount_signed", "debit", "credit", "total", "value",
    "amount_delta", "running_balance"
]
DATE_COLUMN_CANDIDATES = [
    "date", "transaction_date", "posted_date", "entry_date", "posting_date",
    "due_date", "period_start", "period_end", "statement_period_start",
    "statement_period_end"
]
