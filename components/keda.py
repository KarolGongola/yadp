import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from config import config

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.keda_ns_name,
    metadata={
        "name": config.keda_ns_name,
    },
)

keda_release = helm.Release(
    resource_name=config.keda_name,
    chart="keda",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://kedacore.github.io/charts",
    ),
    version="2.16.1",
    values={
        "clusterName": config.k8s_context,
        "clusterDomain": config.domain_name,
    },
)
