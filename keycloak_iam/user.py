import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.provider import master_provider
from keycloak_iam.realm import main_realm

guest_test_email = "guest.test@example.com"
guest_test_user = keycloak.User(
    resource_name=guest_test_email,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    username=guest_test_email,
    email=guest_test_email,
    email_verified=True,
    enabled=True,
    initial_password={
        "value": config.keycloak_guest_test_password,
        "temporary": False,
    },
)
