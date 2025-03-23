import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from config import config
from utils.k8s import get_binary_truststore

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.kafka_ui_ns_name,
    metadata={
        "name": config.kafka_ui_ns_name,
    },
)

if config.root_ca_secret_name:
    truststore_configmap_name = "truststore-configmap"
    truststore_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.kafka_ui_ns_name}-{truststore_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=truststore_configmap_name),
        binary_data={
            "truststore.jks": get_binary_truststore(),
        },
    )

kafka_ui_release = helm.Release(
    resource_name=config.kafka_ui_name,
    chart="kafka-ui",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://kafbat.github.io/helm-charts",
    ),
    version="1.4.11",
    # https://github.com/kafbat/helm-charts/blob/main/charts/kafka-ui/values.yaml
    values={
        "replicaCount": 1,
        "image": {"registry": "docker.io", "repository": "karolgongola/kafka-ui", "tag": "20250325"},
        "ingress": {
            "enabled": True,
            "ingressClassName": "nginx",
            "annotations": {
                "kubernetes.io/ingress.class": "nginx",
                "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                "nginx.ingress.kubernetes.io/affinity": "cookie",
                "nginx.ingress.kubernetes.io/affinity-mode": "balanced",
                "nginx.ingress.kubernetes.io/session-cookie-expires": "172800",
                "nginx.ingress.kubernetes.io/session-cookie-max-age": "172800",
                "nginx.ingress.kubernetes.io/session-cookie-name": "kafbat-ui",
            },
            "host": config.kafka_ui_hostname,
            "tls": {"enabled": True, "secretName": f"{config.kafka_ui_name}-tls"},
        },
        "resources": {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi",
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi",
            },
        },
        "env": [
            # {
            #     "name": "CLASSPATH",
            #     "value": "/",
            # }
            # {
            #     "name": "KAFKA_CLUSTERS_0_SSL_TRUSTSTORELOCATION",
            #     "value": "/truststore.jks",
            # },
            # {
            #     "name": "KAFKA_CLUSTERS_0_SSL_TRUSTSTOREPASSWORD",
            #     "value": "not-needed-pass",
            # },
        ],
        "volumes": [
            {
                "name": "certs-volume",
                "configMap": {
                    "name": truststore_configmap_name,
                },
            }
        ]
        if config.root_ca_secret_name
        else [],
        "volumeMounts": [{"name": "certs-volume", "mountPath": "/home/kafkaui/certs"}] if config.root_ca_secret_name else [],
        "yamlApplicationConfig": {
            "logging": {
                "level": config.log_level.upper(),
            },
            "server": {
                "ssl": {
                    "trust-store": "classpath:truststore.jks",
                    "trust-store-password": "not-needed-pass",
                },
            },
            "http": {
                "client": {
                    "ssl": {
                        "trust-store": "classpath:truststore.jks",
                        "trust-store-password": "not-needed-pass",
                    },
                },
            },
            "auth": {
                "type": "OAUTH2",
                "oauth2": {
                    "client": {
                        "keycloak": {
                            "clientId": "kafka-admin",
                            "clientSecret": "XXX",
                            "scope": "openid",
                            "issuer-uri": "https://keycloak.yadp.localhost/realms/yadp",
                            "user-name-attribute": "preferred_username",
                            "client-name": "keycloak",
                            "provider": "keycloak",
                            "custom-params": {"type": "oauth"},
                        }
                    }
                },
            },
            # auth:
            #   type: OAUTH2
            #   oauth2:
            #     client:
            #       keycloak:
            #         clientId: xxx
            #         clientSecret: yyy
            #         scope: openid
            #         issuer-uri: https://<keycloak_instance>/auth/realms/<realm>
            #         user-name-attribute: preferred_username
            #         client-name: keycloak
            #         provider: keycloak
            #         custom-params:
            #           type: oauth
            "kafka": {
                "clusters": [
                    # {
                    #     "name": config.kafka_name,
                    #     "bootstrapServers": ",".join([f"{broker_host_tamplate.format(nodeId=i)}:443"
                    # for i in range(config.kafka_broker_replicas)]),
                    #     "properties": {
                    #         "security.protocol": "SASL_SSL",
                    #         "sasl.mechanism": "OAUTHBEARER",
                    #         "sasl.jaas.config": 'org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule
                    # required oauth.client.id="kafka-admin" oauth.client.secret="XXX"
                    # oauth.token.endpoint.uri="https://keycloak.yadp.localhost/realms/yadp/protocol/openid-connect/token";',
                    #         "sasl.login.callback.handler.class": "io.strimzi.kafka.oauth.client.JaasClientOauthLoginCallbackHandler",
                    #     }
                    #     # } | ({
                    #     #     "ssl.truststore.location": "classpath:truststore.jks",
                    #     #     "ssl.truststore.password": "not-needed-pass",
                    #     # } if config.root_ca_secret_name else {})
                    # }
                ]
            },
        },
    },
)
