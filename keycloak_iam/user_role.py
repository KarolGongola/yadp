import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.client import kafka_admin_client
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from keycloak_iam.role import kafka_admin_role

kafka_admin_role_mapping = keycloak.UserRoles(
    resource_name=f"{config.realm_name}-kafka-admin-role-mapping",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    user_id=kafka_admin_client.service_account_user_id,
    role_ids=[kafka_admin_role.id],
)
