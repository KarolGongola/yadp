"""Yet Another Data Platform IaaC entrypoint."""

from components import (
    airflow,
    ceph,
    cert_manager,
    ingress_controller,
    kafka,
    kafka_ui,
    keda,
    keycloak,
    monitoring,
    superset,
    trino,
)
from keycloak_iam import (
    client,
    group,
    idp,
    kafka_authorization,
    realm,
    role,
    user,
    user_role,
)
