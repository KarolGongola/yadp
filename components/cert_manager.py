import pulumi
import pulumi_kubernetes as kubernetes

from config import config

# We assume that cert manager namespace exists with root ca secret

cert_manager = kubernetes.helm.v3.Release(
    resource_name=config.cert_manager_name,
    name=config.cert_manager_name,
    chart="cert-manager",
    namespace=config.cert_manager_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="https://charts.jetstack.io",
    ),
    skip_crds=False,
    version="v1.16.2",
    values={
        "installCRDs": True,
    },
)

cluster_issuer = kubernetes.apiextensions.CustomResource(
    resource_name=config.cluster_issuer_name,
    opts=pulumi.ResourceOptions(depends_on=[cert_manager]),
    api_version="cert-manager.io/v1",
    kind="ClusterIssuer",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.cluster_issuer_name,
        namespace=config.cert_manager_ns_name,
    ),
    spec=config.cluster_issuer_spec,
)
