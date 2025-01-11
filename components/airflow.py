import base64
from textwrap import dedent

import pulumi
import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from components.keda import keda_release
from config import config
from keycloak_iam.client import airflow_client, airflow_client_id
from keycloak_iam.role import airflow_admin_role_name, airflow_viewer_role_name
from utils.k8s import get_decoded_root_cert
from utils.pulumi import create_pvc

airflow_db_volume_size = "8Gi"
local_airflow_db_dir = "airflow_db"

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.airflow_ns_name,
    metadata={
        "name": config.airflow_ns_name,
    },
)

airflow_db_pvc = create_pvc(
    namespace_name=config.airflow_ns_name,
    volume_size=airflow_db_volume_size,
    storage_class_name=config.storage_class_name,
    pvc_name="airflow-db-pvc",
    local_persistence_dir=local_airflow_db_dir,
    pv_name="airflow-db-pv",
)

gitsync_secret_name = "gitsync-token"  # noqa: S105 Possible hardcoded password assigned
gitsync_secret = kubernetes.core.v1.Secret(
    resource_name=f"{config.airflow_ns_name}-{gitsync_secret_name}",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=gitsync_secret_name),
    data={
        "GIT_SYNC_USERNAME": base64.b64encode("__token__".encode()).decode(),
        "GIT_SYNC_PASSWORD": base64.b64encode(config.airflow_gitsync_token.encode()).decode(),
        "GITSYNC_USERNAME": base64.b64encode("__token__".encode()).decode(),
        "GITSYNC_PASSWORD": base64.b64encode(config.airflow_gitsync_token.encode()).decode(),
    },
)


def get_webserver_config(client_secret: str) -> str:
    return str(
        dedent(f"""
        import os
        import jwt
        import requests
        import logging
        from base64 import b64decode
        from cryptography.hazmat.primitives import serialization
        from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH
        from airflow import configuration as conf
        from airflow.www.security import AirflowSecurityManager

        log = logging.getLogger(__name__)

        AUTH_TYPE = AUTH_OAUTH
        AUTH_USER_REGISTRATION = True
        AUTH_ROLES_SYNC_AT_LOGIN = True
        AUTH_USER_REGISTRATION_ROLE = "Public"
        OIDC_ISSUER = "https://{config.keycloak_url}/realms/{config.realm_name}"

        # Make sure you create these role on Keycloak
        AUTH_ROLES_MAPPING = {{
            "{airflow_viewer_role_name}": ["Viewer"],
            "{airflow_admin_role_name}": ["Admin"],
            #"User": ["User"],
            #"Public": ["Public"],
            #"Op": ["Op"],
        }}

        OAUTH_PROVIDERS = [
            {{
                "name": "keycloak",
                "icon": "fa-key",
                "token_key": "access_token",
                "remote_app": {{
                    "client_id": "{airflow_client_id}",
                    "client_secret": "{client_secret}",
                    "server_metadata_url": "https://{config.keycloak_url}/realms/{config.realm_name}/.well-known/openid-configuration",
                    "api_base_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect",
                    "client_kwargs": {{"scope": "email profile"}},
                    "access_token_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token",
                    "authorize_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/auth",
                    "request_token_url": None,
                }},
            }}
        ]

        # Fetch public key
        req = requests.get(OIDC_ISSUER)
        key_der_base64 = req.json()["public_key"]
        key_der = b64decode(key_der_base64.encode())
        public_key = serialization.load_der_public_key(key_der)


        class CustomSecurityManager(AirflowSecurityManager):
            def get_oauth_user_info(self, provider, response):
                if provider == "keycloak":
                    token = response["access_token"]
                    me = jwt.decode(token, public_key, algorithms=["HS256", "RS256"], options={{"verify_aud": False}})
                    log.debug("me: {{0}}".format(me))

                    # Extract roles from resource access
                    realm_access = me.get("realm_access", {{}})
                    groups = realm_access.get("roles", [])

                    log.info("groups: {{0}}".format(groups))

                    if not groups:
                        groups = [AUTH_USER_REGISTRATION_ROLE]

                    userinfo = {{
                        "username": me.get("preferred_username"),
                        "email": me.get("email"),
                        "first_name": me.get("given_name"),
                        "last_name": me.get("family_name"),
                        "role_keys": groups,
                    }}

                    log.info("user info: {{0}}".format(userinfo))

                    return userinfo
                else:
                    return {{}}


        # Make sure to replace this with your own implementation of AirflowSecurityManager class
        SECURITY_MANAGER_CLASS = CustomSecurityManager
        """).strip()
    )


if config.root_ca_secret_name:
    certs_configmap_name = "certs-configmap"
    root_ca_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.airflow_ns_name}-{certs_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=certs_configmap_name),
        data={
            "root-ca.pem": get_decoded_root_cert(),
        },
    )

airflow_release = helm.Release(
    opts=pulumi.ResourceOptions(depends_on=[keda_release]),
    resource_name=config.airflow_name,
    chart="airflow",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://airflow.apache.org",
    ),
    version="1.15.0",
    values={
        "config": {
            "scheduler": {
                "min_file_process_interval": 60  # Set your desired interval here
            },
        },
        "postgresql": {
            "enabled": True,
            "primary": {
                "persistence": {
                    "enabled": True,
                    "existingClaim": airflow_db_pvc.metadata["name"],
                },
            },
        },
        "ingress": {
            "web": {
                "enabled": True,
                "host": config.airflow_hostname,
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                },
                "tls": {
                    "enabled": True,
                    "secretName": "airflow-web-tls",
                },
            },
        },
        "createUserJob": {
            "useHelmHooks": False,
            "applyCustomEnv": False,
        },
        "migrateDatabaseJob": {
            "useHelmHooks": False,
            "applyCustomEnv": False,
        },
        "webserver": {
            "webserverConfig": airflow_client.client_secret.apply(get_webserver_config),
            "defaultUser": {
                "enabled": False,
            },
            "env": [
                {
                    "name": "REQUESTS_CA_BUNDLE",
                    "value": "/etc/airflow/certs/root-ca.pem",
                },
                {
                    "name": "AIRFLOW__CORE__LOGGING_LEVEL",
                    "value": "DEBUG",
                },
            ]
            if config.root_ca_secret_name
            else [],
            "extraVolumes": [
                {
                    "name": "certs-volume",
                    "configMap": {
                        "name": certs_configmap_name,
                    },
                }
            ]
            if config.root_ca_secret_name
            else [],
            "extraVolumeMounts": [
                {
                    "name": "certs-volume",
                    "mountPath": "/etc/airflow/certs",
                }
            ]
            if config.root_ca_secret_name
            else [],
        },
        "executor": "CeleryExecutor",
        "workers": {
            "replicas": 0,
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 30,
                "minReplicaCount": 0,
                "maxReplicaCount": 10,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
            "persistence": {
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
        },
        "triggerer": {
            "replicas": 1,
            # "keda": {},
            "persistence": {
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 30,
                "minReplicaCount": 0,
                "maxReplicaCount": 2,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
        },
        "redis": {
            "persistence": {
                "size": "1Gi",
                "storageClassName": config.storage_class_name,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
        },
        "logs": {
            "persistence": {
                "enabled": config.airflow_persistence_enabled,
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
        },
        "dags": {
            "persistence": {
                "enabled": config.airflow_persistence_enabled,
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
            "gitSync": {
                "enabled": True,
                "repo": config.airflow_dags_repo,
                "branch": config.airflow_dags_branch,
                "credentialsSecret": gitsync_secret.metadata["name"],
                "period": "30s",
                "subPath": config.airflow_dags_dir_sub_path,
            },
        },
    },
)
