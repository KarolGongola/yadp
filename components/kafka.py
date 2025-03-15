import base64

import pulumi
import pulumi_kubernetes as kubernetes

from components.ceph import rook_cluster_release
from components.cert_manager import cluster_issuer
from config import config
from keycloak_iam.client import kafka_client
from utils.k8s import get_ca_bundle

bootstrap_host: str = f"bootstrap.{config.kafka_hostname}"
broker_host_tamplate: str = f"broker-{{nodeId}}.{config.kafka_hostname}"


def encode_secret(secret: str) -> str:
    return base64.b64encode(secret.encode()).decode()


namespace = kubernetes.core.v1.Namespace(
    config.kafka_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.kafka_ns_name,
    ),
)

if config.root_ca_secret_name:
    root_ca_key = "root-ca.pem"
    root_ca_secret = kubernetes.core.v1.Secret(
        resource_name=f"{config.kafka_ns_name}-{config.kafka_name}-certs",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=f"{config.kafka_name}-certs"),
        data={
            root_ca_key: base64.b64encode(get_ca_bundle().encode()).decode(),
        },
    )

client_secret_key = "client-secret"  # noqa: S105 Possible hardcoded password
kafka_client_secret = kubernetes.core.v1.Secret(
    resource_name=f"{config.kafka_ns_name}-{config.kafka_name}-client-secret",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=f"{config.kafka_name}-client-secret"),
    data={
        client_secret_key: kafka_client.client_secret.apply(encode_secret),
    },
)

external_certificate_secret_name = f"{config.kafka_name}-external-certificate"
external_certificate = kubernetes.apiextensions.CustomResource(
    resource_name=f"{config.kafka_ns_name}-{config.kafka_name}-external-certificate",
    api_version="cert-manager.io/v1",
    kind="Certificate",
    metadata={"namespace": namespace.metadata["name"], "name": f"{config.kafka_name}-external-certificate"},
    spec={
        "secretName": external_certificate_secret_name,
        "issuerRef": {
            "name": cluster_issuer.metadata["name"],
            "kind": "ClusterIssuer",
            "group": "cert-manager.io",
        },
        "subject": {
            "organizations": [config.realm_name],
        },
        "dnsNames": [bootstrap_host] + [broker_host_tamplate.format(nodeId=i) for i in range(config.kafka_broker_replicas)],
    },
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

cluster_name = f"{config.kafka_name}-main-cluster"
node_pool_name = f"{config.kafka_name}-dual-role"
node_pool = kubernetes.apiextensions.CustomResource(
    resource_name=f"{config.kafka_ns_name}-{node_pool_name}",
    opts=pulumi.ResourceOptions(depends_on=[kafka_release]),
    api_version="kafka.strimzi.io/v1beta2",
    kind="KafkaNodePool",
    metadata={"name": node_pool_name, "namespace": config.kafka_ns_name, "labels": {"strimzi.io/cluster": cluster_name}},
    spec={
        "replicas": config.kafka_broker_replicas,
        "roles": ["controller", "broker"],
        "storage": {
            "type": "jbod",
            "volumes": [
                {
                    "id": 0,
                    "type": "persistent-claim",
                    "size": "100Gi" if not config.use_minimal_storage else "1Gi",
                    "deleteClaim": False,
                    "kraftMetadata": "shared",
                }
            ],
        },
    },
)

authentication = {
    "type": "oauth",
    "validIssuerUri": f"https://{config.keycloak_url}/realms/{config.realm_name}",
    "jwksEndpointUri": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/certs",
    "tokenEndpointUri": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token",
    "clientId": kafka_client.client_id,
    "clientSecret": {"secretName": kafka_client_secret.metadata["name"], "key": client_secret_key},
    "tlsTrustedCertificates": [{"secretName": root_ca_secret.metadata["name"], "certificate": root_ca_key}]
    if config.root_ca_secret_name
    else [],
}

# Add authorization configuration
authorization = {
    "type": "keycloak",
    "tokenEndpointUri": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token",
    "clientId": kafka_client.client_id,
    "delegateToKafkaAcls": True,
    "superUsers": [],
    "tlsTrustedCertificates": [{"secretName": root_ca_secret.metadata["name"], "certificate": root_ca_key}]
    if config.root_ca_secret_name
    else [],
}

kafka_cluster = kubernetes.apiextensions.CustomResource(
    resource_name=f"{config.kafka_ns_name}-{cluster_name}",
    opts=pulumi.ResourceOptions(depends_on=[kafka_release]),
    api_version="kafka.strimzi.io/v1beta2",
    kind="Kafka",
    metadata={
        "name": cluster_name,
        "namespace": config.kafka_ns_name,
        "annotations": {"strimzi.io/node-pools": "enabled", "strimzi.io/kraft": "enabled"},
    },
    spec={
        "kafka": {
            "version": "3.9.0",
            "metadataVersion": "3.9-IV0",
            "listeners": [
                {
                    "name": "internal",
                    "port": 9093,
                    "type": "internal",
                    "tls": False,
                    "authentication": authentication,
                },
                {
                    "name": "external",
                    "port": 9094,
                    "type": "ingress",
                    "tls": True,
                    "configuration": {
                        "bootstrap": {"host": bootstrap_host},
                        "hostTemplate": broker_host_tamplate,
                        "class": "nginx",
                        "brokerCertChainAndKey": {
                            "secretName": external_certificate_secret_name,
                            "certificate": "tls.crt",
                            "key": "tls.key",
                        },
                    },
                    "authentication": authentication,
                },
            ],
            "authorization": authorization,
            "config": {
                "offsets.topic.replication.factor": 1,
                "transaction.state.log.replication.factor": 1,
                "transaction.state.log.min.isr": 1,
                "default.replication.factor": 1,
                "min.insync.replicas": 1,
            },
        },
        "entityOperator": {"topicOperator": {}, "userOperator": {}},
    },
)
