import pulumi
import pulumi_keycloak as keycloak

from components.keycloak import keycloak_release
from config import config

master_provider = keycloak.Provider(
    opts=pulumi.ResourceOptions(depends_on=[keycloak_release]),
    resource_name="master_keycloak_provider",
    url=f"https://{config.keycloak_url}",
    realm="master",
    client_id="admin-cli",
    client_timeout=300,
    username=config.keycloak_admin_login,
    password=config.keycloak_admin_password,
)
