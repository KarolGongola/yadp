import base64
from textwrap import dedent

import pulumi
import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from components.keda import keda_release
from config import config
from keycloak_iam.client import airflow_client
from utils.airflow import airflow_roles_to_create, celery_executor_keda_query, get_webserver_config
from utils.k8s import get_decoded_root_cert
from utils.pulumi import create_pvc

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.airflow_ns_name,
    metadata={
        "name": config.airflow_ns_name,
    },
)

airflow_db_pvc = create_pvc(
    namespace_name=config.airflow_ns_name,
    volume_size="8Gi",
    storage_class_name=config.storage_class_name,
    pvc_name="airflow-db-pvc",
    persistence_dir="airflow_db",
    pv_name="airflow-db-pv",
)

role_creation_script_config_map_name = "role-creation-script"
role_creation_script_config_map = kubernetes.core.v1.ConfigMap(
    resource_name=f"{config.airflow_ns_name}-{role_creation_script_config_map_name}",
    metadata={
        "name": role_creation_script_config_map_name,
        "namespace": namespace.metadata["name"],
    },
    data={
        "create-roles.sh": dedent(f"""
        #!/bin/bash
        ROLES=("{'", "'.join(airflow_roles_to_create)}")

        for ROLE_NAME in "${{ROLES[@]}}"; do
            if ! airflow roles list | grep -q "$ROLE_NAME"; then
                airflow roles create "$ROLE_NAME"
                echo "Role '$ROLE_NAME' created."
            else
                echo "Role '$ROLE_NAME' already exists."
            fi
        done
    """).strip()
    },
)

gitsync_secret_name = "gitsync-token"  # noqa: S105 Possible hardcoded password assigned
gitsync_secret = kubernetes.core.v1.Secret(
    resource_name=f"{config.airflow_ns_name}-{gitsync_secret_name}",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=gitsync_secret_name),
    data={
        "GIT_SYNC_USERNAME": base64.b64encode("__token__".encode()).decode(),
        "GIT_SYNC_PASSWORD": base64.b64encode(config.airflow_gitsync_token.encode()).decode(),
        "GITSYNC_USERNAME": base64.b64encode("__token__".encode()).decode(),
        "GITSYNC_PASSWORD": base64.b64encode(config.airflow_gitsync_token.encode()).decode(),
    },
)

if config.root_ca_secret_name:
    certs_configmap_name = "certs-configmap"
    root_ca_secret = kubernetes.core.v1.ConfigMap(
        resource_name=f"{config.airflow_ns_name}-{certs_configmap_name}",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(namespace=namespace.metadata["name"], name=certs_configmap_name),
        data={
            "root-ca.pem": get_decoded_root_cert(),
        },
    )

airflow_release = helm.Release(
    opts=pulumi.ResourceOptions(depends_on=[keda_release]),
    resource_name=config.airflow_name,
    chart="airflow",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://airflow.apache.org",
    ),
    version="1.15.0",
    values={
        "config": {
            "scheduler": {
                "min_file_process_interval": 60  # Set your desired interval here
            },
            "celery": {
                "worker_concurrency": 8,
            },
        },
        "postgresql": {
            "enabled": True,
            "primary": {
                "persistence": {
                    "enabled": True,
                    "existingClaim": airflow_db_pvc.metadata["name"],
                },
            },
        },
        "ingress": {
            "web": {
                "enabled": True,
                "host": config.airflow_hostname,
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                },
                "tls": {
                    "enabled": True,
                    "secretName": "airflow-web-tls",
                },
            },
        },
        "createUserJob": {
            "useHelmHooks": False,
            "applyCustomEnv": False,
        },
        "migrateDatabaseJob": {
            "useHelmHooks": False,
            "applyCustomEnv": False,
        },
        "webserverSecretKey": config.airflow_webserwer_secret_key,
        "webserver": {
            "webserverConfig": airflow_client.client_secret.apply(get_webserver_config),
            "defaultUser": {
                "enabled": False,
            },
            "args": [
                "bash",
                "-c",
                "cp /etc/scripts/create-roles.sh ./ && chmod +x ./create-roles.sh && ./create-roles.sh && exec airflow webserver",
            ],
            "env": [
                {
                    "name": "REQUESTS_CA_BUNDLE",
                    "value": "/etc/airflow/certs/root-ca.pem",
                },
                {
                    "name": "AIRFLOW__CORE__LOGGING_LEVEL",
                    "value": "DEBUG",
                },
            ]
            if config.root_ca_secret_name
            else [],
            "extraVolumes": [
                {
                    "name": "create-roles-script",
                    "configMap": {
                        "name": role_creation_script_config_map_name,
                    },
                }
            ]
            + [
                {
                    "name": "certs-volume",
                    "configMap": {
                        "name": certs_configmap_name,
                    },
                }
            ]
            if config.root_ca_secret_name
            else [],
            "extraVolumeMounts": [
                {
                    "name": "create-roles-script",
                    "mountPath": "/etc/scripts",
                }
            ]
            + [
                {
                    "name": "certs-volume",
                    "mountPath": "/etc/airflow/certs",
                }
            ]
            if config.root_ca_secret_name
            else [],
        },
        "executor": "CeleryExecutor",
        "workers": {
            "replicas": 0,
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 60,
                "minReplicaCount": 0,
                "maxReplicaCount": 10,
                "query": celery_executor_keda_query,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
            "persistence": {
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
        },
        "scheduler": {
            "replicas": 1,
            "resources": {
                "requests": {
                    "cpu": "250m",
                    "memory": "512Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
        },
        "triggerer": {
            "replicas": 1,
            # "keda": {},
            "persistence": {
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 60,
                "minReplicaCount": 0,
                "maxReplicaCount": 2,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
        },
        "redis": {
            "persistence": {
                "size": "1Gi",
                "storageClassName": config.storage_class_name,
            },
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
                "limits": {
                    "cpu": "1",
                    "memory": "2Gi",
                },
            },
        },
        # Disabled because my storageclass does not support ReadWriteMany, TODO: set logs at s3 or other system
        # "logs": {
        #     "persistence": {
        #         "enabled": config.airflow_persistence_enabled,
        #         "size": "16Gi",
        #         "storageClassName": config.storage_class_name,
        #     },
        # },
        "dags": {
            "persistence": {
                "enabled": config.airflow_persistence_enabled,
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
            "gitSync": {
                "enabled": True,
                "repo": config.airflow_dags_repo,
                "branch": config.airflow_dags_branch,
                "credentialsSecret": gitsync_secret.metadata["name"],
                "period": "30s",
                "subPath": config.airflow_dags_dir_sub_path,
            },
        },
    },
)
