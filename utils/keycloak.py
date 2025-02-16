import contextlib
import time
from typing import Generator

import pulumi
import pulumi_keycloak as keycloak


class RetryError(Exception):
    pass


@contextlib.contextmanager
def retry_on_503(retries: int = 3, delay: int = 2) -> Generator:
    attempt = 0
    while attempt < retries:
        try:
            yield
            break
        except Exception as e:
            if "503" in str(e):
                attempt += 1
                if attempt < retries:
                    time.sleep(delay)
                else:
                    raise RetryError("Max retries reached") from e
            else:
                raise


def get_oidc_client(realm_id: str, client_id: str, keycloak_provider: keycloak.Provider) -> keycloak.openid.AwaitableGetClientResult:
    with retry_on_503(retries=10, delay=5):
        return keycloak.openid.get_client(
            opts=pulumi.InvokeOptions(provider=keycloak_provider),
            realm_id=realm_id,
            client_id=client_id,
        )


def get_client_role(realm_id: str, client_id: str, role_name: str, keycloak_provider: keycloak.Provider) -> keycloak.AwaitableGetRoleResult:
    return keycloak.get_role(
        opts=pulumi.InvokeOptions(provider=keycloak_provider),
        realm_id=realm_id,
        client_id=client_id,
        name=role_name,
    )


def get_role_ids(realm_id: str, roles: dict[str, list[str]], keycloak_provider: keycloak.Provider) -> Generator[str, None, None]:
    for client_name, role_names in roles.items():
        client_id = get_oidc_client(realm_id=realm_id, client_id=client_name, keycloak_provider=keycloak_provider).id
        for role_name in role_names:
            role = get_client_role(realm_id=realm_id, client_id=client_id, role_name=role_name, keycloak_provider=keycloak_provider)
            yield role.id


def assign_roles_to_exiting_users(realm_id: str, provider: keycloak.Provider, role_ids: list[str], users: list[str]) -> None:
    for username in users:
        try:
            user = keycloak.get_user(
                opts=pulumi.InvokeOptions(provider=provider),
                username=username,
                realm_id=realm_id,
            )
            keycloak.user_roles.UserRoles(
                resource_name=f"trusted-guest-user-role-mapping-{username.replace('@', '-').replace('.', '-')}",
                realm_id=realm_id,
                user_id=user.id,
                role_ids=role_ids,
                opts=pulumi.ResourceOptions(provider=provider),
            )
        except Exception as e:
            if f"user with username {username} not found" in str(e):
                pulumi.log.warn(f"Failed to assign role to user {username}: {e}")
            else:
                raise e
