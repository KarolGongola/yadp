"""Yet Another Data Platform IaaC entrypoint."""

from components import (
    cert_manager,
    ingress_controller,
    keycloak,
    trino,
)
from keycloak_iam import (
    client,
    idp,
    realm,
    role,
    user,
    user_role,
)
