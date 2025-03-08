import os
from dataclasses import dataclass, field

import pulumi


@dataclass(kw_only=True)
class Config:
    pulumi_config: pulumi.Config = field(default_factory=pulumi.Config)
    domain_name: str = None
    realm_name: str = "yadp"
    realm_display_name: str = "Yet Another Data Platform"
    log_level: str = "info"
    root_ca_secret_name: str = None
    storage_class_name: str = "rook-ceph-block"
    use_minimal_storage: bool = False
    bucket_storage_class_name: str = "rook-ceph-bucket"
    cert_manager_ns_name: str = "cert-manager"
    cert_manager_name: str = "cert-manager"
    cluster_issuer_name: str = "cluster-issuer"
    ingress_ns_name: str = "ingress-controller"
    ingress_controller_name: str = "nginx-ingress"
    keycloak_admin_login: str = "admin"
    keycloak_ns_name: str = "keycloak"
    keycloak_name: str = "keycloak"
    trino_ns_name: str = "trino"
    trino_name: str = "trino"
    keda_ns_name: str = "keda"
    keda_name: str = "keda"
    airflow_ns_name: str = "airflow"
    airflow_name: str = "airflow"
    airflow_gitsync_token: str = field(default_factory=lambda: os.getenv("AIRFLOW_GITSYNC_TOKEN"))
    airflow_dags_repo: str = "https://github.com/KarolGongola/yadp-dags.git"
    airflow_dags_dir_sub_path: str = "dags"
    airflow_dags_branch: str = "main"
    ceph_ns_name: str = "rook-ceph"
    ceph_name: str = "ceph"
    ceph_failure_domain: str = "host"
    ceph_object_expiration_days: int = 30
    ceph_osd_memory_target: str = "4Gi"
    ceph_osd_memory_limit: str = "4Gi"
    monitoring_ns_name: str = "monitoring"
    superset_ns_name: str = "superset"
    superset_name: str = "superset"
    kafka_ns_name: str = "kafka"
    kafka_name: str = "kafka"
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

    @property
    def ceph_dashboard_hostname(self) -> str:
        return f"ceph.{self.domain_name}"

    @property
    def ceph_rgw_hostname(self) -> str:
        return f"s3.{self.domain_name}"

    @property
    def grafana_hostname(self) -> str:
        return f"grafana.{self.domain_name}"

    @property
    def superset_hostname(self) -> str:
        return f"superset.{self.domain_name}"


@dataclass(kw_only=True)
class LocalConfig(Config):
    domain_name: str = "yadp.localhost"
    k8s_context: str = "local"
    log_level: str = "debug"
    root_ca_secret_name: str = "root-ca"  # noqa: S105 Possible hardcoded password
    airflow_dags_branch: str = "dev"
    ceph_failure_domain: str = "osd"
    ceph_object_expiration_days: int = 1
    ceph_osd_memory_target: str = "1Gi"
    ceph_osd_memory_limit: str = "1200Mi"
    use_minimal_storage: bool = True

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

    @property
    def grafana_admin_password(self) -> str:
        return os.getenv("LOCAL_GRAFANA_ADMIN_PASSWORD")

    @property
    def superset_secret_key(self) -> str:
        return os.getenv("LOCAL_SUPERSET_SECRET_KEY")

    @property
    def superset_postgres_password(self) -> str:
        return os.getenv("LOCAL_SUPERSET_POSTGRES_PASSWORD")

    @property
    def keycloak_superset_svc_user_password(self) -> str:
        return os.getenv("LOCAL_KEYCLOAK_SUPERSET_SVC_USER_PASSWORD")


@dataclass(kw_only=True)
class HomelabConfig(Config):
    domain_name: str = "yadp.xyz"
    k8s_context: str = "eagle"
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
    ceph_osd_memory_target: str = "1Gi"
    ceph_osd_memory_limit: str = "1200Mi"

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

    @property
    def grafana_admin_password(self) -> str:
        return os.getenv("HOMELAB_GRAFANA_ADMIN_PASSWORD")

    @property
    def superset_secret_key(self) -> str:
        return os.getenv("HOMELAB_SUPERSET_SECRET_KEY")

    @property
    def superset_postgres_password(self) -> str:
        return os.getenv("HOMELAB_SUPERSET_POSTGRES_PASSWORD")

    @property
    def keycloak_superset_svc_user_password(self) -> str:
        return os.getenv("HOMELAB_KEYCLOAK_SUPERSET_SVC_USER_PASSWORD")


pulumi_stack = pulumi.get_stack()
config = HomelabConfig() if pulumi_stack == "homelab" else LocalConfig()
