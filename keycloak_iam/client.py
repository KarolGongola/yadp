import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm

security_admin_console_client_id = "security-admin-console"
security_admin_console_client = keycloak.openid.Client(
    resource_name=security_admin_console_client_id,
    realm_id=main_realm.realm,
    client_id=security_admin_console_client_id,
    access_type="PUBLIC",
    name="Keycloak Admin Console",
    # For now we need to manually set "Always display in UI" to true,
    # because it is not supported by pulumi and it is not appearing in Applications page before first usage
    import_=True,
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

trino_client_id = "trino"
trino_client = keycloak.openid.Client(
    resource_name=trino_client_id,
    name="Trino",
    realm_id=main_realm.realm,
    client_id=trino_client_id,
    access_type="CONFIDENTIAL",
    standard_flow_enabled=True,
    base_url=f"https://{config.trino_hostname}",
    root_url=f"https://{config.trino_hostname}",
    valid_redirect_uris=["/*"],
    valid_post_logout_redirect_uris=["/*"],
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

airflow_client_id = "airflow"
airflow_client = keycloak.openid.Client(
    resource_name=airflow_client_id,
    name="Airflow",
    realm_id=main_realm.realm,
    client_id=airflow_client_id,
    access_type="CONFIDENTIAL",
    standard_flow_enabled=True,
    base_url=f"https://{config.airflow_hostname}",
    root_url=f"https://{config.airflow_hostname}",
    valid_redirect_uris=["/*"],
    valid_post_logout_redirect_uris=["/*"],
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)
