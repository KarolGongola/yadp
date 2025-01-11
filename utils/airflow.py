from textwrap import dedent

from config import config
from keycloak_iam.client import airflow_client_id
from keycloak_iam.role import airflow_admin_role_name, airflow_trusted_viewer_role_name, airflow_viewer_role_name

celery_executor_keda_query: str = dedent("""
    SELECT ceil(COUNT(*)::decimal / {{ .Values.config.celery.worker_concurrency }})
    FROM task_instance
    WHERE state IN ('running' ,'queued', 'scheduled', 'restarting')
    {{- if or (contains "CeleryKubernetesExecutor" .Values.executor)
    (contains "KubernetesExecutor" .Values.executor) }}
    AND queue != '{{ .Values.config.celery_kubernetes_executor.kubernetes_queue }}'
    {{- end }}
    """).strip()

trusted_viever_role_name: str = "Trusted Viewer"
airflow_roles_to_create: list[str] = [trusted_viever_role_name]


def get_webserver_config(client_secret: str) -> str:
    return dedent(f"""
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
            "{airflow_trusted_viewer_role_name}": ["{trusted_viever_role_name}"],
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
