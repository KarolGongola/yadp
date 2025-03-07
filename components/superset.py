from textwrap import dedent

import pulumi
import pulumi_kubernetes as kubernetes

from components.ceph import rook_cluster_release
from components.cert_manager import cluster_issuer
from config import config
from keycloak_iam.client import superset_client
from keycloak_iam.role import superset_admin_role_name, superset_trusted_viewer_role_name
from utils.k8s import get_ca_bundle

namespace = kubernetes.core.v1.Namespace(
    config.superset_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.superset_ns_name,
    ),
)

if config.root_ca_secret_name:
    certs_configmap_name = "certs-configmap"
    root_ca_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.superset_ns_name}-{certs_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=certs_configmap_name),
        data={
            "root-ca.pem": get_ca_bundle(),
        },
    )

superset_release_name = f"{config.superset_ns_name}-{config.superset_name}"
superset_release = kubernetes.helm.v3.Release(
    resource_name=superset_release_name,
    opts=pulumi.ResourceOptions(depends_on=[rook_cluster_release]),
    name=config.superset_name,
    chart="superset",
    namespace=config.superset_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="http://apache.github.io/superset",
    ),
    version="0.14.0",
    # https://github.com/apache/superset/blob/master/helm/superset/values.yaml
    values={
        "serviceAccount": {
            "create": True,
        },
        "image": {
            "repository": "apache/superset",
            "tag": "b3dfd4930acbbcd9dd74bf7d9c02d00b2b818292-py311",
        },
        "bootstrapScript": dedent("""
            #!/bin/bash
            apt-get update && apt-get install -y gcc &&
            uv pip install .[postgres] trino Authlib Flask-OIDC &&
            if [ ! -f ~/bootstrap ]; then echo "Running Superset with uid {{ .Values.runAsUser }}" > ~/bootstrap; fi
            """).strip(),
        "extraEnv": {
            "DEBUG": config.log_level.lower() == "debug",
        },
        "extraEnvRaw": [
            {
                "name": "REQUESTS_CA_BUNDLE",
                "value": "/etc/superset/certs/root-ca.pem",
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
                "mountPath": "/etc/superset/certs",
            }
        ]
        if config.root_ca_secret_name
        else [],
        "extraSecretEnv": {
            "SUPERSET_SECRET_KEY": config.superset_secret_key,
            "KEYCLOAK_CLIENT_ID": superset_client.client_id,
            "KEYCLOAK_CLIENT_SECRET": superset_client.client_secret,
        },
        # TODO: Use internal trino service url instead of public one
        "extraConfigs": {
            "import_datasources.yaml": dedent(f"""
                databases:
                - database_name: Trino tpcds
                  sqlalchemy_uri: trino://{config.trino_hostname}:443/tpcds
                  cache_timeout: null
                  expose_in_sqllab: true
                  allow_run_async: false
                  allow_ctas: true
                  allow_cvas: true
                  allow_dml: true
                  allow_csv_upload: false
                  extra: |
                    {{
                      "allows_virtual_table_explore": true,
                      "cost_estimate_enabled": true,
                      "schema_options": {{
                        "expand_rows": true
                      }},
                      "engine_params": {{
                        "connect_args": {{
                          "http_scheme": "https"
                        }}
                      }}
                    }}
                  impersonate_user: true
            """).strip()
        },
        "configOverrides": {
            "secret": dedent(f"""
                SECRET_KEY = '{config.superset_secret_key}'
            """).strip(),
            "oauth_clients": dedent(f"""
                DATABASE_OAUTH2_REDIRECT_URI = "https://{config.superset_hostname}/api/v1/database/oauth2/"
                DATABASE_OAUTH2_CLIENTS = {{
                    'Trino': {{
                        'id': os.getenv("KEYCLOAK_CLIENT_ID"),
                        'secret': os.getenv("KEYCLOAK_CLIENT_SECRET"),
                        'scope': 'openid email offline_access roles profile',
                        'redirect_uri': "https://{config.superset_hostname}/api/v1/database/oauth2/",
                        'authorization_request_uri': 'https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/auth',
                        'token_request_uri': 'https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token',
                        'request_content_type': 'data' # keycloak doesn't accept application/json body.
                    }}
                }}
            """).strip(),
            "enable_oauth": dedent(f"""
                ENABLE_PROXY_FIX = True

                import requests
                import jwt
                import logging
                import os
                from base64 import b64decode
                from cryptography.hazmat.primitives import serialization
                from flask_appbuilder.security.manager import AUTH_OAUTH
                from superset.security import SupersetSecurityManager

                AUTH_TYPE = AUTH_OAUTH
                OAUTH_PROVIDERS = [
                    {{
                        "name": "keycloak",
                        "icon": "fa-key",
                        "token_key": "access_token",
                        "remote_app": {{
                            "client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
                            "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
                            "server_metadata_url": "https://{config.keycloak_url}/realms/{config.realm_name}/.well-known/openid-configuration",
                            "api_base_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect",
                            "client_kwargs": {{"scope": "openid email profile roles"}},
                            "access_token_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token",
                            "authorize_url": "https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/auth",
                            "request_token_url": None,
                        }},
                    }}
                ]
                # Will allow user self registration, allowing to create Flask users from Authorized User
                AUTH_USER_REGISTRATION = True

                # The default user self registration role
                AUTH_USER_REGISTRATION_ROLE = "Public"

                # Map Authlib roles to superset roles
                AUTH_ROLE_PUBLIC = "Public"
                PUBLIC_ROLE_LIKE = "Gamma"

                # Map Authlib roles to superset roles
                AUTH_ROLES_MAPPING = {{
                    '{superset_admin_role_name}': ['Admin'],
                    '{superset_trusted_viewer_role_name}': ['Gamma', 'sql_lab', 'trusted_viewer'],
                }}

                # If we should replace ALL the user's roles each login, or only add new ones
                AUTH_ROLES_SYNC_AT_LOGIN = True

                # Fetch public key
                req = requests.get("https://{config.keycloak_url}/realms/{config.realm_name}")
                key_der_base64 = req.json()["public_key"]
                key_der = b64decode(key_der_base64.encode())
                public_key = serialization.load_der_public_key(key_der)

                class CustomSecurityManager(SupersetSecurityManager):
                    def get_oauth_user_info(self, provider, response):
                        if provider == "keycloak":
                            token = response["access_token"]
                            me = jwt.decode(token, public_key, algorithms=["HS256", "RS256"], options={{"verify_aud": False}})
                            logging.debug("me: {{0}}".format(me))

                            # Extract roles from resource access
                            realm_access = me.get("realm_access", {{}})
                            roles = realm_access.get("roles", [])

                            logging.info("roles: {{0}}".format(roles))

                            if not roles:
                                roles = [AUTH_USER_REGISTRATION_ROLE]

                            userinfo = {{
                                "username": me.get("preferred_username"),
                                "email": me.get("email"),
                                "first_name": me.get("given_name"),
                                "last_name": me.get("family_name"),
                                "role_keys": roles,
                            }}

                            logging.info("user info: {{0}}".format(userinfo))

                            return userinfo
                        else:
                            return {{}}

                # Use custom security manager
                CUSTOM_SECURITY_MANAGER = CustomSecurityManager
            """).strip(),
        },
        "ingress": {
            "enabled": True,
            "ingressClassName": "nginx",
            "hosts": [config.superset_hostname],
            "annotations": {
                "kubernetes.io/ingress.class": "nginx",
                "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
            },
            "tls": [
                {
                    "hosts": [config.superset_hostname],
                    "secretName": f"{config.superset_name}-tls-secret",
                },
            ],
        },
        "postgresql": {
            "enabled": True,
            "postgresqlPassword": config.superset_postgres_password,
            "primary": {
                "persistence": {
                    "enabled": True,
                    "storageClass": config.storage_class_name,
                },
            },
        },
        "redis": {
            "enabled": True,
            "master": {
                "persistence": {
                    "enabled": True,
                    "storageClass": config.storage_class_name,
                },
            },
        },
    },
)
