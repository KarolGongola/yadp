from config import config
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from keycloak_iam.role import admin_role, airflow_admin_role, airflow_viewer_role, trusted_guest_role
from utils.keycloak import assign_roles_to_exiting_users

# TODO: For now there is assign role to existing users only
assign_roles_to_exiting_users(
    realm_id=main_realm.realm,
    provider=master_provider,
    role_ids=[trusted_guest_role.id, airflow_viewer_role.id],
    users=config.trusted_guest_users,
)
assign_roles_to_exiting_users(
    realm_id=main_realm.realm,
    provider=master_provider,
    role_ids=[admin_role.id, airflow_admin_role.id],
    users=config.admin_users,
)
