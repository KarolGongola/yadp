import pulumi
import pulumi_keycloak as keycloak

from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from utils.keycloak import get_realm_role, get_role_ids

all_built_in_client_roles = {
    "account": [
        "delete-account",
        "manage-account",
        "manage-account-links",
        "manage-consent",
        "view-applications",
        "view-consent",
        "view-groups",
        "view-profile",
    ],
    "broker": [
        "read-token",
    ],
    "realm-management": [
        "create-client",
        "impersonation",
        "manage-authorization",
        "manage-clients",
        "manage-events",
        "manage-identity-providers",
        "manage-realm",
        "manage-users",
        "query-clients",
        "query-groups",
        "query-realms",
        "query-users",
        "realm-admin",
        "view-authorization",
        "view-clients",
        "view-events",
        "view-identity-providers",
        "view-realm",
        "view-users",
    ],
}

trusted_guest_built_in_client_roles = {
    "account": [
        "delete-account",
        "manage-account",
        "manage-account-links",
        "manage-consent",
        "view-applications",
        "view-consent",
        "view-groups",
        "view-profile",
    ],
    "realm-management": [
        "query-clients",
        "query-groups",
        "query-realms",
        "query-users",
        "view-authorization",
        "view-clients",
        "view-events",
        "view-identity-providers",
        "view-realm",
        "view-users",
    ],
}

offline_access_role = get_realm_role(
    realm_id=main_realm.realm,
    role_name="offline_access",
    keycloak_provider=master_provider,
)

admin_role_name = "admin"
admin_role = keycloak.Role(
    resource_name=admin_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=admin_role_name,
    description="YADP Admin",
    composite_roles=list(get_role_ids(realm_id=main_realm.realm, roles=all_built_in_client_roles, keycloak_provider=master_provider)),
)

trusted_guest_role_name = "trusted-guest"
trusted_guest_role = keycloak.Role(
    resource_name=trusted_guest_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=trusted_guest_role_name,
    description="YADP Trusted Guest",
    composite_roles=list(
        get_role_ids(realm_id=main_realm.realm, roles=trusted_guest_built_in_client_roles, keycloak_provider=master_provider)
    ),
)

airflow_viewer_role_name = "airflow-viewer"
airflow_viewer_role = keycloak.Role(
    resource_name=airflow_viewer_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=airflow_viewer_role_name,
    description="YADP Airflow Viewer",
)

airflow_trusted_viewer_role_name = "airflow-trusted-viewer"
airflow_trusted_viewer_role = keycloak.Role(
    resource_name=airflow_trusted_viewer_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=airflow_trusted_viewer_role_name,
    description="YADP Airflow Trusted Viewer",
)

airflow_admin_role_name = "airflow-admin"
airflow_admin_role = keycloak.Role(
    resource_name=airflow_admin_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=airflow_admin_role_name,
    description="YADP Airflow Admin",
)

grafana_viewer_role_name = "grafana-viewer"
grafana_viewer_role = keycloak.Role(
    resource_name=grafana_viewer_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=grafana_viewer_role_name,
    description="YADP Grafana Viewer",
)

grafana_editor_role_name = "grafana-editor"
grafana_editor_role = keycloak.Role(
    resource_name=grafana_editor_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=grafana_editor_role_name,
    description="YADP Grafana Editor",
)

grafana_admin_role_name = "grafana-admin"
grafana_admin_role = keycloak.Role(
    resource_name=grafana_admin_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=grafana_admin_role_name,
    description="YADP Grafana Admin",
)

superset_admin_role_name = "superset-admin"
superset_admin_role = keycloak.Role(
    resource_name=superset_admin_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=superset_admin_role_name,
    description="YADP Superset Admin",
)

superset_trusted_viewer_role_name = "superset-trusted-viewer"
superset_trusted_viewer_role = keycloak.Role(
    resource_name=superset_trusted_viewer_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=superset_trusted_viewer_role_name,
    description="YADP Superset Trusted Viewer",
)

default_roles = keycloak.DefaultRoles(
    resource_name="default-roles",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    default_roles=[
        "offline_access",
        "uma_authorization",
        airflow_viewer_role.name,
        grafana_viewer_role.name,
    ],
)
