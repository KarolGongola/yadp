import base64
import json
from textwrap import dedent

import pulumi
import pulumi_kubernetes as kubernetes
import pulumi_kubernetes.helm.v3 as helm

from components.ceph import region_name
from components.cert_manager import cluster_issuer
from components.keda import keda_release
from config import config
from keycloak_iam.client import airflow_client
from utils.airflow import airflow_roles_to_create, celery_executor_keda_query, get_webserver_config
from utils.k8s import get_decoded_root_cert

namespace = kubernetes.core.v1.Namespace(
    resource_name=config.airflow_ns_name,
    metadata={
        "name": config.airflow_ns_name,
    },
)

logs_bucket_name = f"{config.airflow_ns_name}-{config.airflow_name}-logs"
logs_bucket = kubernetes.apiextensions.CustomResource(
    resource_name=logs_bucket_name,
    api_version="objectbucket.io/v1alpha1",
    kind="ObjectBucketClaim",
    metadata={
        "name": logs_bucket_name,
        "namespace": namespace.metadata["name"],
    },
    spec={
        "bucketName": logs_bucket_name,
        "storageClassName": config.bucket_storage_class_name,
        "additionalConfig": {
            "bucketMaxObjects": "10000",
            "bucketMaxSize": "64G",
            "bucketLifecycle": json.dumps(
                {
                    "Rules": [
                        {
                            "ID": "ExpireAfterNDays",
                            "Status": "Enabled",
                            "Prefix": "",
                            "Expiration": {"Days": config.ceph_object_expiration_days},
                        }
                    ]
                }
            ),
        },
    },
)

logs_bucket_secret = kubernetes.core.v1.Secret.get(
    resource_name=f"{logs_bucket_name}-secret",
    id=f"{config.airflow_ns_name}/{logs_bucket_name}",
    opts=pulumi.ResourceOptions(depends_on=[logs_bucket]),
)

connections_secret_name = "connections"  # noqa: S105 Possible hardcoded password assigned
connections_secret = kubernetes.core.v1.Secret(
    resource_name=f"{config.airflow_ns_name}-{config.airflow_name}-{connections_secret_name}",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        name=connections_secret_name,
        namespace=namespace.metadata["name"],
    ),
    string_data={
        "AIRFLOW_CONN_LOGS_S3": pulumi.Output.all(
            logs_bucket_secret.data["AWS_ACCESS_KEY_ID"], logs_bucket_secret.data["AWS_SECRET_ACCESS_KEY"]
        ).apply(
            lambda args: json.dumps(
                {
                    "conn_type": "aws",
                    "login": base64.b64decode(args[0]).decode("utf-8"),
                    "password": base64.b64decode(args[1]).decode("utf-8"),
                    "extra": {"region_name": region_name, "endpoint_url": f"https://{config.ceph_rgw_hostname}"}
                    | ({"verify": "/etc/airflow/certs/root-ca.pem"} if config.root_ca_secret_name else {}),
                }
                if args
                else None
            )
        ),
    },
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
    opts=pulumi.ResourceOptions(depends_on=[keda_release, connections_secret]),
    resource_name=config.airflow_name,
    chart="airflow",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://airflow.apache.org",
    ),
    version="1.15.0",
    values={
        "config": {
            "scheduler": {"min_file_process_interval": 60},
            "celery": {
                "worker_concurrency": 8,
            },
            "logging": {
                "remote_logging": True,
                "remote_base_log_folder": f"s3://{logs_bucket_name}",
                "remote_log_conn_id": "logs_s3",
                "encrypt_s3_logs": False,
            },
        },
        "postgresql": {
            "enabled": True,
            "global": {
                "defaultStorageClass": config.storage_class_name,
            },
        },
        "extraEnvFrom": json.dumps(
            [
                {
                    "secretRef": {
                        "name": connections_secret_name,
                    },
                },
            ]
        ),
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
        "volumes": [
            {
                "name": "create-roles-script",
                "configMap": {
                    "name": role_creation_script_config_map_name,
                },
            }
        ]
        + (
            [
                {
                    "name": "certs-volume",
                    "configMap": {
                        "name": certs_configmap_name,
                    },
                }
            ]
            if config.root_ca_secret_name
            else []
        ),
        "volumeMounts": [
            {
                "name": "create-roles-script",
                "mountPath": "/etc/scripts",
            }
        ]
        + (
            [
                {
                    "name": "certs-volume",
                    "mountPath": "/etc/airflow/certs",
                }
            ]
            if config.root_ca_secret_name
            else []
        ),
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
        },
        "executor": "CeleryExecutor",
        "workers": {
            "replicas": 0,
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 120,
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
            "persistence": {
                "size": "16Gi",
                "storageClassName": config.storage_class_name,
            },
            "keda": {
                "enabled": True,
                "pollingInterval": 10,
                "cooldownPeriod": 120,
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
        "dags": {
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
