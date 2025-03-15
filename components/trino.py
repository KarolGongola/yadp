import json

import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from config import config
from keycloak_iam.client import trino_client, trino_client_id
from utils.k8s import get_ca_bundle

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.trino_ns_name,
    metadata={
        "name": config.trino_ns_name,
    },
)

if config.root_ca_secret_name:
    certs_configmap_name = "certs-configmap"
    root_ca_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.trino_ns_name}-{certs_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=certs_configmap_name),
        data={
            "root-ca.pem": get_ca_bundle(),
        },
    )


def get_coordinator_extra_config(client_secret: str) -> str:
    return "\n".join(
        [
            f"http-server.authentication.oauth2.issuer=https://{config.keycloak_url}/realms/{config.realm_name}",
            f"http-server.authentication.oauth2.client-id={trino_client_id}",
            f"http-server.authentication.oauth2.client-secret={client_secret}",
            "http-server.authentication.oauth2.scopes=openid",
            "http-server.authentication.oauth2.principal-field=email",
            "web-ui.enabled=true",
            "web-ui.authentication.type=oauth2",
        ]
    )


trino_release = helm.Release(
    resource_name=config.trino_name,
    chart="trino",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://trinodb.github.io/charts",
    ),
    version="1.35.0",
    values={
        "ingress": {
            "enabled": True,
            "annotations": {
                "kubernetes.io/ingress.class": "nginx",
                "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
            },
            "hosts": [{"host": config.trino_hostname, "paths": [{"path": "/", "pathType": "ImplementationSpecific"}]}],
            "tls": [
                kubernetes.networking.v1.IngressTLSArgs(hosts=[config.trino_hostname], secret_name="trino-tls-secret")  # noqa: S106 Possible hardcoded password assigned to argument
            ],
        },
        "server": {
            "config": {
                "authenticationType": "oauth2",
                "https": {
                    "enable": True,
                },
            },
            "workers": 0,
            "coordinatorExtraConfig": trino_client.client_secret.apply(get_coordinator_extra_config),
        },
        "worker": {
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "500m",
                    "memory": "1024Mi",
                },
            },
            "jvm": {"maxHeapSize": "512M"},
            "config": {
                "query": {
                    "maxMemoryPerNode": "256MB",
                }
            },
        },
        "keda": {
            "enabled": True,
            "pollInterval": "30s",
            "coolDownPeriod": "300s",
            "minReplicaCount": 0,
            "maxReplicaCount": 4,
        },
        "additionalConfigProperties": [
            "internal-communication.shared-secret=test",
            "http-server.process-forwarded=true",
        ],
        "additionalLogProperties": [
            f"io.airflift={config.log_level.upper()}",
            f"io.trino={config.log_level.upper()}",
            f"io.trino.server.security.oauth2={config.log_level.upper()}",
            f"io.trino.server.ui.OAuth2WebUiAuthenticationFilter={config.log_level.upper()}",
        ],
        "coordinator": {
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "500m",
                    "memory": "1024Mi",
                },
            },
            "jvm": {"maxHeapSize": "512M"},
            "config": {
                "query": {
                    "maxMemoryPerNode": "256MB",
                }
            },
            "additionalJVMConfig": [
                "-Djavax.net.ssl.trustStore=etc/certs/root-ca.pem",
            ],
            "additionalVolumes": [
                {
                    "name": "certs-volume",
                    "configMap": {
                        "name": certs_configmap_name,
                    },
                }
            ],
            "additionalVolumeMounts": [
                {
                    "name": "certs-volume",
                    "mountPath": "/etc/trino/certs",
                }
            ],
        }
        if config.root_ca_secret_name
        else {},
        "accessControl": {
            "type": "configmap",
            "refreshPeriod": "60s",
            "configFile": "rules.json",
            "rules": {
                "rules.json": json.dumps(
                    {
                        "catalogs": [{"user": user, "catalog": "(mysql|system|tpcds|tpch)", "allow": "all"} for user in config.admin_users]
                        + [
                            {"user": user, "catalog": "(mysql|system|tpcds|tpch)", "allow": "read-only"}
                            for user in config.trusted_guest_users
                        ],
                        "schemas": [{"user": user, "schema": ".*", "owner": True} for user in config.admin_users]
                        + [{"user": user, "owner": False} for user in config.trusted_guest_users],
                    }
                )
            },
        },
    },
)
