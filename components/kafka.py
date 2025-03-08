import pulumi
import pulumi_kubernetes as kubernetes

from components.ceph import rook_cluster_release
from config import config

namespace = kubernetes.core.v1.Namespace(
    config.kafka_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.kafka_ns_name,
    ),
)

kafka_release = kubernetes.helm.v3.Release(
    resource_name=f"{config.kafka_ns_name}-{config.kafka_name}-operator",
    opts=pulumi.ResourceOptions(depends_on=[rook_cluster_release]),
    name=f"{config.kafka_name}-operator",
    chart="oci://quay.io/strimzi-helm/strimzi-kafka-operator",
    namespace=config.kafka_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="",
    ),
    version="0.45.0",
    # https://github.com/strimzi/strimzi-kafka-operator/blob/main/helm-charts/helm3/strimzi-kafka-operator/values.yaml
    values={
        "replicas": 1,
        "watchAnyNamespace": False,
        "logLevel": config.log_level.upper(),
        "dashboards": {
            "enabled": True,
        },
    },
)
