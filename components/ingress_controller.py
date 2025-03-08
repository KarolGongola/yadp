import pulumi
import pulumi_kubernetes as kubernetes

from components.cert_manager import cluster_issuer
from config import config

ingress_ns = kubernetes.core.v1.Namespace(
    config.ingress_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.ingress_ns_name,
    ),
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
    values={"controller": {"extraArgs": {"enable-ssl-passthrough": "true"}}},
)

default_domain_ingress_name = "default-domain-redirect"
default_domain_ingress = kubernetes.networking.v1.Ingress(
    resource_name=default_domain_ingress_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=default_domain_ingress_name,
        namespace=config.ingress_ns_name,
        annotations={
            "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
            "nginx.ingress.kubernetes.io/permanent-redirect": f"https://{config.keycloak_url}/realms/yadp/account/applications",
        },
    ),
    spec=kubernetes.networking.v1.IngressSpecArgs(
        ingress_class_name="nginx",
        tls=[
            kubernetes.networking.v1.IngressTLSArgs(
                hosts=[config.domain_name],
                secret_name="default-doman-tls-secret",  # noqa: S106 -> Name of the secret created by Cert Manager
            ),
        ],
        rules=[
            kubernetes.networking.v1.IngressRuleArgs(
                host=config.domain_name,
                http=kubernetes.networking.v1.HTTPIngressRuleValueArgs(
                    paths=[
                        kubernetes.networking.v1.HTTPIngressPathArgs(
                            path="/",
                            path_type="Prefix",
                            backend=kubernetes.networking.v1.IngressBackendArgs(
                                service=kubernetes.networking.v1.IngressServiceBackendArgs(
                                    name="dummy-service",
                                    port=kubernetes.networking.v1.ServiceBackendPortArgs(
                                        number=80,
                                    ),
                                ),
                            ),
                        ),
                    ],
                ),
            ),
        ],
    ),
    opts=pulumi.ResourceOptions(depends_on=[ingress_controller]),
)
