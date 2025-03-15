import pulumi
import pulumi_keycloak as keycloak

from keycloak_iam.client import kafka_client
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm
from keycloak_iam.role import (
    kafka_admin_role,
)

# ============================================================
# Resources
# ============================================================
topic_all_resource = keycloak.openid.ClientAuthorizationResource(
    resource_name="kafka-topic-all-resource",
    realm_id=main_realm.realm,
    resource_server_id=kafka_client.id,
    name="Topic:*",
    type="Topic",
    owner_managed_access=False,
    display_name="All topics",
    scopes=["Create", "Delete", "Describe", "Write", "IdempotentWrite", "Read", "Alter", "DescribeConfigs", "AlterConfigs"],
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

group_all_resource = keycloak.openid.ClientAuthorizationResource(
    resource_name="kafka-group-all-resource",
    realm_id=main_realm.realm,
    resource_server_id=kafka_client.id,
    name="Group:*",
    type="Group",
    owner_managed_access=False,
    display_name="All consumer groups",
    scopes=["Describe", "Delete", "Read"],
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

cluster_resource = keycloak.openid.ClientAuthorizationResource(
    resource_name="kafka-cluster-resource",
    realm_id=main_realm.realm,
    resource_server_id=kafka_client.id,
    name="Cluster:*",
    type="Cluster",
    owner_managed_access=False,
    display_name="All Clusters",
    scopes=["DescribeConfigs", "AlterConfigs", "ClusterAction", "IdempotentWrite"],
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

# ============================================================
# Policies
# ============================================================
admin_role_policy = keycloak.openid.ClientRolePolicy(
    resource_name="kafka-admin-role-policy",
    realm_id=main_realm.realm,
    resource_server_id=kafka_client.id,
    name="Kafka Admin Role Policy",
    roles=[
        keycloak.openid.ClientRolePolicyRoleArgs(
            id=kafka_admin_role.id,
            required=True,
        ),
    ],
    logic="POSITIVE",
    decision_strategy="UNANIMOUS",
    type="role",
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)

# ============================================================
# Permissions
# ============================================================
admin_permission = keycloak.openid.ClientAuthorizationPermission(
    resource_name="kafka-admin-permission",
    realm_id=main_realm.realm,
    resource_server_id=kafka_client.id,
    name="Kafka Admin Permission",
    resources=[topic_all_resource.id, group_all_resource.id, cluster_resource.id],
    policies=[
        admin_role_policy.id,
    ],
    decision_strategy="UNANIMOUS",
    opts=pulumi.ResourceOptions(
        provider=master_provider,
    ),
)
