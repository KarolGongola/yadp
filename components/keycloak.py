import pulumi_kubernetes as kubernetes

from components.cert_manager import cluster_issuer
from config import config
from utils.pulumi import create_pvc

import_export_volume_size = "1Gi"
local_export_import_dir = "keycloak_realms"

keycloak_ns = kubernetes.core.v1.Namespace(
    config.keycloak_ns_name,
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=config.keycloak_ns_name,
    ),
)

import_export_pvc = create_pvc(
    namespace_name=config.keycloak_ns_name,
    volume_size=import_export_volume_size,
    storage_class_name=config.storage_class_name,
    pvc_name="import-export-pvc",
    local_persistence_dir=local_export_import_dir,
    pv_name="import-export-pv",
)

keycloak_release = kubernetes.helm.v3.Release(
    resource_name=config.keycloak_name,
    name=config.keycloak_name,
    chart="oci://registry-1.docker.io/bitnamicharts/keycloak",
    namespace=config.keycloak_ns_name,
    repository_opts=kubernetes.helm.v3.RepositoryOptsArgs(
        repo="",
    ),
    values={
        "global.defaultStorageClass": config.storage_class_name,
        "proxyAddressForwarding": True,
        "ingress": {
            "enabled": True,
            "hostname": config.keycloak_url,
            "annotations": {
                "kubernetes.io/ingress.class": "nginx",
                "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
            },
            "tls": True,
        },
        "production": True,
        "proxyHeaders": "xforwarded",
        "auth": {
            "adminUser": config.keycloak_admin_login,
            "adminPassword": config.keycloak_admin_password,
        },
        "extraEnvVars": config.keycloak_extraEnvVars,
        "extraVolumes": [
            {
                "name": "import-export-volume",
                "persistentVolumeClaim": {
                    "claimName": import_export_pvc.metadata["name"],
                },
            },
        ],
        "extraVolumeMounts": [
            {
                "name": "import-export-volume",
                "mountPath": "/export",
            },
            {
                "name": "import-export-volume",
                "mountPath": "/opt/bitnami/keycloak/data/import",
            },
        ],
        # # Disablle cache and change readOnlyRootFilesystem to False just to be able to export realms
        # # https://github.com/bitnami/charts/issues/13105#issuecomment-1375422340
        # "cache": {
        #     "enabled": False
        # },
        # "containerSecurityContext": {
        #     "readOnlyRootFilesystem": False,
        # },
    },
    version="24.3.2",
    skip_crds=False,
)
