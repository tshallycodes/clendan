from dataclasses import dataclass, field as dc_field


@dataclass
class OAuthConfig:
    auth_url: str
    token_url: str
    scope: str
    client_id_attr: str   # attribute name on Settings
    client_secret_attr: str
    extra_auth_params: dict = dc_field(default_factory=dict)


OAUTH_REGISTRY: dict[str, OAuthConfig] = {
    "sage": OAuthConfig(
        auth_url="https://www.sageone.com/oauth2/auth/central",
        token_url="https://oauth.accounting.sage.com/token",
        scope="readonly",
        client_id_attr="sage_client_id",
        client_secret_attr="sage_client_secret",
    ),
    "wave": OAuthConfig(
        auth_url="https://api.waveapps.com/oauth2/authorize",
        token_url="https://api.waveapps.com/oauth2/token",
        scope="account:read customer:read invoice:read payment:read",
        client_id_attr="wave_client_id",
        client_secret_attr="wave_client_secret",
    ),
    "wise": OAuthConfig(
        auth_url="https://api.wise.com/oauth/authorize",
        token_url="https://api.wise.com/v1/oauth2/token",
        scope="transfers:read balances:read accounts:read",
        client_id_attr="wise_client_id",
        client_secret_attr="wise_client_secret",
    ),
    # Reuses existing microsoft_client_id / microsoft_client_secret
    "dynamics365": OAuthConfig(
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scope="https://globaldisco.crm.dynamics.com/user_impersonation offline_access",
        client_id_attr="microsoft_client_id",
        client_secret_attr="microsoft_client_secret",
        extra_auth_params={"response_mode": "query"},
    ),
    "dropbox": OAuthConfig(
        auth_url="https://www.dropbox.com/oauth2/authorize",
        token_url="https://api.dropboxapi.com/oauth2/token",
        scope="files.metadata.read files.content.read",
        client_id_attr="dropbox_client_id",
        client_secret_attr="dropbox_client_secret",
        extra_auth_params={"token_access_type": "offline"},
    ),
    # Reuses existing microsoft_client_id / microsoft_client_secret
    "onedrive": OAuthConfig(
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scope="Files.Read.All offline_access",
        client_id_attr="microsoft_client_id",
        client_secret_attr="microsoft_client_secret",
    ),
}
