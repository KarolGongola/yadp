import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm

github_identity_provider = keycloak.oidc.IdentityProvider(
    resource_name="github",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm=main_realm.realm,
    alias="github",
    provider_id="github",
    display_name="GitHub",
    enabled=True,
    trust_email=True,
    first_broker_login_flow_alias="first broker login",
    authorization_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",  # noqa: S106 Possible hardcoded password assigned to argument
    client_id=config.github_app_client_id,
    client_secret=config.github_app_client_secret,
    disable_user_info=True,
    default_scopes="user:email",
)
