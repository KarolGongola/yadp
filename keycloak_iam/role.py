import pulumi
import pulumi_keycloak as keycloak

from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from utils.keycloak import get_role_ids

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

admin_role_name = "admin"
admin_role = keycloak.Role(
    resource_name=admin_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=admin_role_name,
    description="YADP Admin",
    composite_roles=list(
        get_role_ids(realm_id=main_realm.realm, roles=all_built_in_client_roles, keycloak_provider=master_provider)
    ),
)

trusted_guest_role_name = "trusted-guest"
trusted_guest_role = keycloak.Role(
    resource_name=trusted_guest_role_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=trusted_guest_role_name,
    description="YADP Trusted Guest",
    composite_roles=list(
        get_role_ids(
            realm_id=main_realm.realm, roles=trusted_guest_built_in_client_roles, keycloak_provider=master_provider
        )
    ),
)