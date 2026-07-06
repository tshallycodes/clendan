class IntegrationStatus:
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"
    NOT_CONNECTED = "not_connected"
    CONNECTING = "connecting"


class TransactionStatus:
    PENDING = "pending"
    CATEGORISED = "categorised"
    MATCHED = "matched"
    BLOCKED = "blocked"


class ConnectorType:
    PLAID = "plaid"
    TRUELAYER = "truelayer"
    MONO = "mono"
    XERO = "xero"
    FRESHBOOKS = "freshbooks"
    QUICKBOOKS = "quickbooks"
    STRIPE = "stripe"
    GOCARDLESS = "gocardless"
    ADYEN = "adyen"
    WISE = "wise"
    SQUARE = "square"
    PAYPAL = "paypal"
    NETSUITE = "netsuite"
    SAP = "sap"
    DYNAMICS365 = "dynamics365"
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    GOOGLE_DRIVE = "google-drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    CODAT = "codat"
    SAGE = "sage"


class Pagination:
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200
    MAX_SYNC_LOG_LIMIT = 20
