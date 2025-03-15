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


def get_realm_role(realm_id: str, role_name: str, keycloak_provider: keycloak.Provider) -> keycloak.AwaitableGetRoleResult:
    return keycloak.get_role(
        opts=pulumi.InvokeOptions(provider=keycloak_provider),
        realm_id=realm_id,
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


def filter_existing_users(users_list: list[str], realm_id: str, provider: keycloak.Provider) -> list[str]:
    """Filter a list of usernames to include only existing users in the realm."""
    # We'll create a pulumi Output for each username
    username_outputs = []

    for username in users_list:
        # Create a dynamic Output that resolves to the username or None
        def create_check_for_user(username: str) -> pulumi.Output[str]:
            def check_user_exists() -> str | None:
                try:
                    # Try to get the user - this will throw an error if the user doesn't exist
                    keycloak.get_user(realm_id=realm_id, username=username, opts=pulumi.InvokeOptions(provider=provider))
                    return username
                except Exception as e:
                    pulumi.log.warn(f"User '{username}' not found in Keycloak: {str(e)}")
                    return None

            # Create an Output from this function
            return pulumi.Output.from_input(check_user_exists())

        # Add this username's Output to our list
        username_outputs.append(create_check_for_user(username))

    # Combine all the Outputs and filter out Nones
    return pulumi.Output.all(*username_outputs).apply(lambda usernames: [u for u in usernames if u is not None])
