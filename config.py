import os
from dataclasses import dataclass, field
from pathlib import Path

import pulumi


@dataclass(kw_only=True)
class Config:
    pulumi_config: pulumi.Config = field(default_factory=pulumi.Config)
    domain_name: str = None
    realm_name: str = "yadp"
    realm_display_name: str = "Yet Another Data Platform"
    protect_persisted_resources: bool = True
    log_level: str = "info"
    root_ca_secret_name: str = None
    root_ca_path: str = None
    storage_class_name: str = None
    local_persistence_dir: str = None
    cert_manager_ns_name: str = "cert-manager"
    cert_manager_name: str = "cert-manager"
    cluster_issuer_name: str = "cluster-issuer"
    ingress_ns_name: str = "ingress-controller"
    ingress_controller_name: str = "nginx-ingress"
    keycloak_admin_login: str = "admin"
    keycloak_ns_name: str = "keycloak"
    keycloak_name: str = "keycloak"
    keycloak_extraEnvVars: list = field(default_factory=list)  # noqa: N815 Mixed case variable name
    trino_ns_name: str = "trino"
    trino_name: str = "trino"
    keda_ns_name: str = "keda"
    keda_name: str = "keda"
    airflow_ns_name: str = "airflow"
    airflow_name: str = "airflow"
    airflow_persistence_enabled: bool = True
    airflow_gitsync_token: str = field(default_factory=lambda: os.getenv("AIRFLOW_GITSYNC_TOKEN"))
    airflow_dags_repo: str = "https://github.com/KarolGongola/yadp-dags.git"
    airflow_dags_dir_sub_path: str = "dags"
    airflow_dags_branch: str = "main"
    admin_users: list[str] = field(
        default_factory=lambda: [
            "karol.gongola@gmail.com",
        ]
    )
    trusted_guest_users: list[str] = field(
        default_factory=lambda: [
            "gongola.karol@gmail.com",
        ]
    )

    @property
    def keycloak_url(self) -> str:
        return f"keycloak.{self.domain_name}"

    @property
    def trino_hostname(self) -> str:
        return f"trino.{self.domain_name}"

    @property
    def airflow_hostname(self) -> str:
        return f"airflow.{self.domain_name}"


@dataclass(kw_only=True)
class LocalConfig(Config):
    domain_name: str = "yadp.localhost"
    k8s_context: str = "local"
    protect_persisted_resources: bool = False
    log_level: str = "debug"
    root_ca_secret_name: str = "root-ca"  # noqa: S105 Possible hardcoded password
    root_ca_path: str = "/usr/local/share/ca-certificates/yadp-rootCA.crt"
    storage_class_name: str = "local-path"
    local_persistence_dir: str = field(default_factory=Path("~/yadp_k3s_persistence_dir").expanduser)
    keycloak_extraEnvVars: list = field(  # noqa: N815 Mixed case variable name
        default_factory=list,  # Change to enable importing realms
    )
    airflow_persistence_enabled: bool = False
    airflow_dags_branch: str = "dev"

    @property
    def cluster_issuer_spec(self) -> dict:
        return {
            "ca": {
                "secretName": self.root_ca_secret_name,
            },
        }

    @property
    def keycloak_admin_password(self) -> str:
        return os.getenv("LOCAL_KEYCLOAK_ADMIN_PASSWORD")

    @property
    def keycloak_guest_test_password(self) -> str:
        return os.getenv("LOCAL_KEYCLOAK_GUEST_TEST_PASSWORD")

    @property
    def github_app_client_id(self) -> str:
        return os.getenv("LOCAL_GITHUB_APP_CLIENT_ID")

    @property
    def github_app_client_secret(self) -> str:
        return os.getenv("LOCAL_GITHUB_APP_CLIENT_SECRET")

    @property
    def airflow_webserwer_secret_key(self) -> str:
        return os.getenv("LOCAL_AIRFLOW_WEBSERVER_SECRET_KEY")


@dataclass(kw_only=True)
class HomelabConfig(Config):
    domain_name: str = "yadp.xyz"
    k8s_context: str = "eagle"
    storage_class_name: str = "freenas-iscsi-csi"
    cluster_issuer_spec: dict = field(
        default_factory=lambda: {
            "acme": {
                "server": "https://acme-v02.api.letsencrypt.org/directory",
                "email": "karol.gongola@gmail.com",
                "privateKeySecretRef": {
                    "name": "letsencrypt-account-key",
                },
                "solvers": [
                    {
                        "http01": {
                            "ingress": {
                                "class": "nginx",
                            },
                        },
                    },
                ],
            },
        },
    )

    @property
    def keycloak_admin_password(self) -> str:
        return os.getenv("HOMELAB_KEYCLOAK_ADMIN_PASSWORD")

    @property
    def keycloak_guest_test_password(self) -> str:
        return os.getenv("HOMELAB_KEYCLOAK_GUEST_TEST_PASSWORD")

    @property
    def github_app_client_id(self) -> str:
        return os.getenv("HOMELAB_GITHUB_APP_CLIENT_ID")

    @property
    def github_app_client_secret(self) -> str:
        return os.getenv("HOMELAB_GITHUB_APP_CLIENT_SECRET")

    @property
    def airflow_webserwer_secret_key(self) -> str:
        return os.getenv("HOMELAB_AIRFLOW_WEBSERVER_SECRET_KEY")


pulumi_stack = pulumi.get_stack()
config = HomelabConfig() if pulumi_stack == "homelab" else LocalConfig()
