import pulumi
import pulumi_kubernetes as kubernetes

from components.ceph import rook_cluster_release
from components.cert_manager import cluster_issuer
from config import config

keycloak_ns = kubernetes.core.v1.Namespace(
    config.keycloak_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.keycloak_ns_name,
    ),
)

keycloak_release = kubernetes.helm.v3.Release(
    resource_name=config.keycloak_name,
    opts=pulumi.ResourceOptions(depends_on=[rook_cluster_release]),
    name=config.keycloak_name,
    chart="oci://registry-1.docker.io/bitnamicharts/keycloak",
    namespace=config.keycloak_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="",
    ),
    # https://github.com/bitnami/charts/blob/main/bitnami/keycloak/values.yaml
    values={
        "global.defaultStorageClass": config.storage_class_name,
        "proxyAddressForwarding": True,
        "ingress": {
            "enabled": True,
            "hostname": config.keycloak_url,
            "annotations": {
                "kubernetes.io/ingress.class": "nginx",
                "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
            },
            "tls": True,
        },
        "production": True,
        "proxyHeaders": "xforwarded",
        "auth": {
            "adminUser": config.keycloak_admin_login,
            "adminPassword": config.keycloak_admin_password,
        },
        "extraEnvVars": config.keycloak_extraEnvVars,
        "logging": {
            "level": config.log_level.upper(),
        },
        "metrics": {
            "serviceMonitor": {
                "enabled": True,
            },
        },
    },
    version="24.4.10",
    skip_crds=False,
)
