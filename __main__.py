"""Yet Another Data Platform IaaC entrypoint."""

from components import (
    airflow,
    ceph,
    cert_manager,
    ingress_controller,
    keda,
    keycloak,
    monitoring,
    superset,
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
