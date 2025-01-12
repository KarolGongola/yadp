import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from config import config

minio_console_hostname = f"console-{config.domain_name}"

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.minio_ns_name,
    metadata={
        "name": config.minio_ns_name,
    },
)

minio_operator_release = helm.Release(
    resource_name=f"{config.minio_ns_name}-{config.minio_name}-operator",
    chart="operator",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://operator.min.io",
    ),
    version="6.0.4",
    values={
        "operator": {
            "replicaCount": 1,
            "resources": {
                "requests": {
                    "cpu": "200m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "400m",
                    "memory": "512Mi",
                },
            },
        },
    },
)

minio_tenant_release = helm.Release(
    resource_name=f"{config.minio_ns_name}-{config.minio_name}-tenant",
    chart="tenant",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://operator.min.io",
    ),
    version="6.0.4",
    values={
        "tenant": {
            "name": config.minio_name,
            "configuration": {
                "name": f"{config.minio_name}-env-configuration",  # TODO: Create a secret with this name
            },
            "pools": [
                {"servers": 1, "name": "pool-0", "volumesPerServer": 1, "size": "16Gi", "storageClassName": config.storage_class_name},
            ],
            "buckets": [
                {
                    "name": "test-bucket",
                    "objectLock": False,
                    "region": "default",
                },
            ],
            "users": [],
        },
        "ingress": {
            "api": {
                "enabled": True,
                "ingressClassName": "nginx",
                "labels": {},
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                    "nginx.ingress.kubernetes.io/backend-protocol": "HTTPS",
                },
                "tls": [
                    kubernetes.networking.v1.IngressTLSArgs(hosts=[config.minio_hostname], secret_name="myminio-tls-secret")  # noqa: S106 Possible hardcoded password assigned to argument
                ],
                "host": config.minio_hostname,
            },
            "console": {
                "enabled": True,
                "ingressClassName": "nginx",
                "labels": {},
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                    "nginx.ingress.kubernetes.io/backend-protocol": "HTTPS",
                },
                "tls": [
                    kubernetes.networking.v1.IngressTLSArgs(hosts=[minio_console_hostname], secret_name="myminio-console-tls-secret")  # noqa: S106 Possible hardcoded password assigned to argument
                ],
                "host": minio_console_hostname,
            },
        },
    },
)
