import pulumi
import pulumi_kubernetes as kubernetes
from components.cert_manager import cluster_issuer
from config import config


ingress_ns = kubernetes.core.v1.Namespace(
    config.ingress_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.ingress_ns_name,
    )
)


ingress_controller = kubernetes.helm.v3.Release(
    resource_name=config.ingress_controller_name,
    opts=pulumi.ResourceOptions(depends_on=[cluster_issuer]),
    name=config.ingress_controller_name,
    chart="ingress-nginx",
    namespace=config.ingress_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="https://kubernetes.github.io/ingress-nginx",
    ),
    skip_crds=False,
    version="4.11.4",
)
