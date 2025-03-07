import pulumi_kubernetes as kubernetes
import requests

from components.cert_manager import cluster_issuer
from config import config
from keycloak_iam.client import grafana_client
from keycloak_iam.role import grafana_admin_role_name, grafana_editor_role_name, grafana_viewer_role_name
from utils.k8s import get_ca_bundle

# TODO: To let grafana dashboard use SSO with Keycloak,
# we need go to Keycloak admin console:
# Client Scopes -> roles -> Mappers -> realm roles
# then manually enable "Add to userinfo" and Save

dashboard_label = "grafana_dashboard"
dashboard_label_value = "1"

namespace = kubernetes.core.v1.Namespace(
    config.monitoring_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.monitoring_ns_name,
    ),
)

if config.root_ca_secret_name:
    certs_configmap_name = "certs-configmap"
    root_ca_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.monitoring_ns_name}-{certs_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=certs_configmap_name),
        data={
            "root-ca.crt": get_ca_bundle(),
        },
    )


def get_ceph_dashboards_data(files: list[str]) -> dict:
    dashboards = {}
    for f in files:
        url = f"https://raw.githubusercontent.com/ceph/ceph/refs/heads/main/monitoring/ceph-mixin/dashboards_out/{f}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dashboard_content = response.text
        dashboards[f"ceph-{f}"] = dashboard_content
    return dashboards


dashboards_configmap_name: str = "dashboards-configmap"
dashboards_configmap = kubernetes.core.v1.ConfigMap(
    resource_name=f"{config.monitoring_ns_name}-{dashboards_configmap_name}",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=dashboards_configmap_name,
        namespace=config.monitoring_ns_name,
        labels={
            dashboard_label: dashboard_label_value,
        },
    ),
    data=get_ceph_dashboards_data(
        files=[
            "ceph-cluster-advanced.json",
            "ceph-cluster.json",
            "cephfs-overview.json",
            "host-details.json",
            "hosts-overview.json",
            "multi-cluster-overview.json",
            "osd-device-details.json",
            "osds-overview.json",
            "pool-detail.json",
            "pool-overview.json",
            "radosgw-detail.json",
            "radosgw-overview.json",
            "radosgw-sync-overview.json",
            "rbd-details.json",
            "rbd-overview.json",
            "rgw-s3-analytics.json",
        ]
    ),
)

monitoring_release_name = f"{config.monitoring_ns_name}-monitoring"
monitoring_release = kubernetes.helm.v3.Release(
    resource_name=monitoring_release_name,
    name=monitoring_release_name,
    namespace=config.monitoring_ns_name,
    chart="kube-prometheus-stack",
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="https://prometheus-community.github.io/helm-charts",
    ),
    version="69.3.3",
    # https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml
    values={
        "crds": {
            "enabled": True,
            "upgradeJob": {
                "enabled": False,
            },
        },
        "alertmanager": {
            "enabled": True,
            "ingres": {
                "enabled": False,
            },
            "alertmanagerSpec": {
                "logLevel": config.log_level.lower(),
                "replicas": 1,
                "retenion": "120h",
                "storage": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "storageClassName": config.storage_class_name,
                            "resources": {
                                "requests": {
                                    "storage": "16Gi" if not config.use_minimal_storage else "1Gi",
                                },
                            },
                        },
                    },
                },
            },
        },
        "grafana": {
            "enabled": True,
            "adminUser": "admin",
            "adminPassword": config.grafana_admin_password,
            "ingress": {
                "enabled": True,
                "ingressClassName": "nginx",
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                },
                "hosts": [config.grafana_hostname],
                "tls": [
                    {
                        "secretName": "grafana-tls",
                        "hosts": [config.grafana_hostname],
                    },
                ],
            },
            "persistence": {
                "enabled": True,
                "storageClassName": config.storage_class_name,
                "accessModes": ["ReadWriteOnce"],
                "size": "16Gi" if not config.use_minimal_storage else "1Gi",
            },
            "grafana.ini": {
                "grafana_net": "",
                "log": {
                    "level": config.log_level.lower(),
                },
                "server": {
                    "root_url": f"https://{config.grafana_hostname}",
                },
                "auth.generic_oauth": {
                    "enabled": "true",
                    "name": "Keycloak-OAuth",
                    "allow_sign_up": "true",
                    "allow_assign_grafana_admin": "true",
                    "use_refresh_token": "true",
                    "role_attribute_strict": "true",
                    "scopes": "openid email profile roles",
                    "email_attribute_path": "email",
                    "login_attribute_path": "username",
                    "name_attribute_path": "full_name",
                    "role_attribute_path": f"contains(realm_access.roles[*], '{grafana_admin_role_name}') && 'GrafanaAdmin' "
                    f"|| contains(realm_access.roles[*], '{grafana_editor_role_name}') && 'Editor' "
                    f"|| contains(realm_access.roles[*], '{grafana_viewer_role_name}') && 'Viewer'",
                    "auth_url": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/auth",
                    "token_url": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/token",
                    "api_url": f"https://{config.keycloak_url}/realms/{config.realm_name}/protocol/openid-connect/userinfo",
                    "redirect_uri": f"https://{config.keycloak_url}/login/generic_oauth",
                    "tls_client_ca": "/etc/ssl/cert.pem",
                },
            },
            "sidecar": {
                "dashboards": {
                    "enabled": True,
                    "label": dashboard_label,
                    "labelValue": dashboard_label_value,
                },
            },
            "env": {
                "GF_AUTH_GENERIC_OAUTH_CLIENT_ID": grafana_client.client_id,
                "GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET": grafana_client.client_secret,
            },
            "extraConfigmapMounts": [
                {
                    "name": certs_configmap_name,
                    "mountPath": "/etc/ssl/cert.pem",
                    "subPath": "root-ca.crt",
                    "configMap": certs_configmap_name,
                    "readOnly": True,
                },
            ]
            if config.root_ca_secret_name
            else [],
        },
        "kubeApiServer": {
            "enabled": True,
        },
        "kubelet": {
            "enabled": True,
        },
        "kubeControllerManager": {
            "enabled": True,
        },
        "coreDns": {
            "enabled": True,
        },
        "kubeDns": {
            "enabled": True,
        },
        "kubeEtcd": {
            "enabled": True,
        },
        "kubeScheduler": {
            "enabled": True,
        },
        "kubeProxy": {
            "enabled": True,
        },
        "kubeMetrics": {
            "enabled": True,
        },
        "nodeExporter": {
            "enabled": True,
        },
        "prometheusOperator": {
            "enabled": True,
        },
        "prometheus": {
            "enabled": True,
            "prometheusSpec": {
                "logLevel": config.log_level.lower(),
                "replicas": 1,
                "shards": 1,
                "retenion": "10d",
                "retentionSize": "60GiB" if not config.use_minimal_storage else "1GiB",
                "storageSpec": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "storageClassName": config.storage_class_name,
                            "resources": {
                                "requests": {
                                    "storage": "64Gi" if not config.use_minimal_storage else "2Gi",
                                },
                            },
                        },
                    },
                },
                "serviceMonitorSelectorNilUsesHelmValues": False,
                "ruleSelectorNilUsesHelmValues": False,
                "podMonitorSelectorNilUsesHelmValues": False,
                "probeSelectorNilUsesHelmValues": False,
                "scrapeConfigSelectorNilUsesHelmValues": False,
            },
        },
    },
    skip_crds=False,
)
