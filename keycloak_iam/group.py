import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from keycloak_iam.role import (
    airflow_admin_role,
    airflow_trusted_viewer_role,
    airflow_viewer_role,
    grafana_admin_role,
    grafana_editor_role,
    grafana_viewer_role,
    keycloak_admin_role,
    keycloak_trusted_guest_role,
    offline_access_role,
    superset_admin_role,
    superset_trusted_viewer_role,
)
from utils.keycloak import filter_existing_users

# ================================================================
# Groups
# ================================================================
admin_group_name = "admin"
admin_group = keycloak.Group(
    resource_name=f"{config.realm_name}-{admin_group_name}",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=admin_group_name,
)

trusted_viewer_group_name = "trusted-viewer"
trusted_viewer_group = keycloak.Group(
    resource_name=f"{config.realm_name}-{trusted_viewer_group_name}",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=trusted_viewer_group_name,
)

viewer_group_name = "viewer"
viewer_group = keycloak.Group(
    resource_name=f"{config.realm_name}-{viewer_group_name}",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    name=viewer_group_name,
)

# ================================================================
# Assign roles to groups
# ================================================================
viewer_group_role_mapping = keycloak.GroupRoles(
    resource_name=f"{config.realm_name}-{viewer_group_name}-roles",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_id=viewer_group.id,
    role_ids=[
        offline_access_role.id,
        airflow_viewer_role.id,
        grafana_viewer_role.id,
    ],
)

trusted_viewer_group_role_mapping = keycloak.GroupRoles(
    resource_name=f"{config.realm_name}-{trusted_viewer_group_name}-roles",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_id=trusted_viewer_group.id,
    role_ids=[
        offline_access_role.id,
        keycloak_trusted_guest_role.id,
        airflow_trusted_viewer_role.id,
        airflow_viewer_role.id,
        grafana_editor_role.id,
        superset_trusted_viewer_role.id,
    ],
)

admin_group_role_mapping = keycloak.GroupRoles(
    resource_name=f"{config.realm_name}-{admin_group_name}-roles",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_id=admin_group.id,
    role_ids=[
        offline_access_role.id,
        keycloak_admin_role.id,
        airflow_admin_role.id,
        grafana_admin_role.id,
        superset_admin_role.id,
    ],
)

# ================================================================
# Default groups
# ================================================================
default_groups = keycloak.DefaultGroups(
    resource_name=f"{config.realm_name}-default-groups",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_ids=[
        viewer_group.id,
    ],
)

# ================================================================
# Add users to groups
# ================================================================
admin_group_memberships = keycloak.GroupMemberships(
    resource_name=f"{config.realm_name}-{admin_group_name}-users",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_id=admin_group.id,
    members=filter_existing_users(users_list=config.admin_users, realm_id=main_realm.realm, provider=master_provider),
)

trusted_viewer_group_memberships = keycloak.GroupMemberships(
    resource_name=f"{config.realm_name}-{trusted_viewer_group_name}-users",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    group_id=trusted_viewer_group.id,
    members=filter_existing_users(users_list=config.trusted_guest_users, realm_id=main_realm.realm, provider=master_provider),
)
