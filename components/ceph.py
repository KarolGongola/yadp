from textwrap import dedent

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm

from components.cert_manager import cluster_issuer
from config import config

# Initial password to dashboard for admin user can be obtained this way:
# kubectl -n rook-ceph get secret rook-ceph-dashboard-password -o jsonpath="{['data']['password']}" | base64 --decode && echo

## To run ceph at less than 3 nodes, we need to modify the crushmap
## We need to do it in toolbox pod after cluster is reconciled by operator
# ceph osd getcrushmap -o crushmap.cm
# crushtool --decompile crushmap.cm -o crushmap.txt
# Change host -> osd in replicated_rule
# crushtool --compile crushmap.txt -o new_crushmap.cm
# ceph osd setcrushmap -i new_crushmap.cm

chart_version = "1.16.3"
object_store_name = "ceph-objectstore"
region_name = "us-east-1"

namespace = k8s.core.v1.Namespace(
    resource_name=config.ceph_ns_name,
    metadata={
        "name": config.ceph_ns_name,
    },
)

rook_operator_release = helm.Release(
    resource_name=f"{config.ceph_ns_name}-{config.ceph_name}-operator",
    chart="rook-ceph",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://charts.rook.io/release",
    ),
    version=chart_version,
    values={
        "crds": {
            "create": True,  # TODO: CRDs are not deleted when deleting release and cannot be reused
        },
        "resources": {
            "requests": {
                "cpu": "200m",
                "memory": "128Mi",
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi",
            },
        },
        "logLevel": config.log_level.upper(),
        "csi": {
            "enableRbdDriver": True,
            "enableCephfsDriver": False,
            "disableCsiDriver": False,
            "nfs": {
                "enabled": False,
            },
        },
        "enableDiscoveryDaemon": True,
        "monitoring": {
            "enabled": True,
        },
    },
)

rook_cluster_release = helm.Release(
    resource_name=f"{config.ceph_ns_name}-{config.ceph_name}-cluster",
    opts=pulumi.ResourceOptions(depends_on=[rook_operator_release]),
    chart="rook-ceph-cluster",
    namespace=namespace.metadata["name"],
    repository_opts=helm.RepositoryOptsArgs(
        repo="https://charts.rook.io/release",
    ),
    version=chart_version,
    allow_null_values=True,  # added to force overrides for arrays
    # https://github.com/rook/rook/blob/master/deploy/charts/rook-ceph-cluster/values.yaml
    values={
        "operatorNamespace": namespace.metadata["name"],
        "clusterName": config.ceph_name,
        "configOverride": dedent(f"""
            [global]
            mon_max_pg_per_osd = 512
            mon_allow_pool_delete = true
            osd_pool_default_size = 3
            osd_pool_default_min_size = 2
            [mgr]
            mgr/crash/warn_recent_interval = 1
            [osd]
            osd_memory_target = {config.ceph_osd_memory_target}
            """),
        "toolbox": {
            "enabled": True,
        },
        # TODO: Deploy prometheus CRDs before enabling ceph monitoring
        # Before it is done, we need to disable monitoring below to install whole setup,
        # then enable it and apply changes
        "monitoring": {
            "enabled": True,
            "metricsDisabled": False,
            "createPrometheusRules": True,
        },
        "cephClusterSpec": {
            "cephVersion": {
                "image": "quay.io/ceph/ceph:v19.2.0",
            },
            "dataDirHostPath": f"/var/lib/rook/{config.ceph_ns_name}-{config.ceph_name}",
            "dashboard": {
                "enabled": True,
                "ssl": False,
            },
            "mon": {
                "count": 1,
                "allowMultiplePerNode": False,
            },
            "mgr": {
                "count": 1,
            },
            "crashCollector": {
                "disable": False,
            },
            "logCollector": {
                "enabled": False,
            },
            "resources": {
                "osd": {
                    "limits": {
                        "memory": config.ceph_osd_memory_limit,
                    },
                    "requests": {
                        "cpu": "300m",
                        "memory": config.ceph_osd_memory_limit,
                    },
                },
            },
            "storage": {
                "useAllNodes": True,
                "useAllDevices": True,
                "config": {
                    "crushRoot": "default",
                },
            },
        },
        "ingress": {
            "dashboard": {
                "ingressClassName": "nginx",
                "host": {
                    "name": config.ceph_dashboard_hostname,
                },
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                },
                "tls": [
                    {
                        "hosts": [config.ceph_dashboard_hostname],
                        "secretName": f"{config.ceph_name}-dashboard-tls",
                    }
                ],
            },
        },
        "cephBlockPools": [],
        "cephFileSystems": [],
        "cephObjectStores": [
            {
                "name": object_store_name,
                "spec": {
                    "metadataPool": {
                        "failureDomain": config.ceph_failure_domain,
                        "replicated": {
                            "size": 3,
                        },
                    },
                    "dataPool": {
                        "failureDomain": config.ceph_failure_domain,
                        "erasureCoded": {
                            "dataChunks": 2,
                            "codingChunks": 1,
                        },
                        "parameters": {
                            "bulk": "true",
                        },
                    },
                    "preservePoolsOnDelete": False,
                    "gateway": {
                        "port": 80,
                        "resources": {
                            "limits": {
                                "memory": "2Gi",
                            },
                            "requests": {
                                "cpu": "500m",
                                "memory": "1Gi",
                            },
                        },
                        "instances": 1,
                        "priorityClassName": "system-cluster-critical",
                    },
                },
                "storageClass": {
                    "name": config.bucket_storage_class_name,
                    "enabled": True,
                    "reclaimPolicy": "Delete",
                    "volumeBindingMode": "Immediate",
                    "parameters": {
                        "region": region_name,
                    },
                },
                "ingress": {
                    "enabled": True,
                    "annotations": {
                        "kubernetes.io/ingress.class": "nginx",
                        "cert-manager.io/cluster-issuer": cluster_issuer.metadata["name"],
                        "nginx.ingress.kubernetes.io/proxy-body-size": "0",
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "600",
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "600",
                    },
                    "host": {
                        "name": config.ceph_rgw_hostname,
                    },
                    "tls": [
                        {
                            "hosts": [config.ceph_rgw_hostname],
                            "secretName": f"{config.ceph_name}-rgw-tls",
                        }
                    ],
                    "ingressClassName": "nginx",
                },
            },
        ],
        "cephECBlockPools": [
            {
                "name": "default-ec-pool",
                "spec": {
                    "metadataPool": {
                        "failureDomain": config.ceph_failure_domain,
                        "replicated": {
                            "size": 3,
                        },
                    },
                    "dataPool": {
                        "failureDomain": config.ceph_failure_domain,
                        "erasureCoded": {
                            "dataChunks": 2,
                            "codingChunks": 1,
                        },
                    },
                },
                "parameters": {
                    "clusterID": f"{config.ceph_ns_name}",
                    "imageFormat": "2",
                    "imageFeatures": "layering",
                },
                "storageClass": {
                    "provisioner": "ceph-operator.rbd.csi.ceph.com",
                    "enabled": True,
                    "name": config.storage_class_name,
                    "isDefault": True,
                    "allowVolumeExpansion": True,
                    "reclaimPolicy": "Delete",
                },
            },
        ],
    },
)

# pulumi_ceph_user_name = "pulumi-ceph-user"
# pulumi_ceph_user = k8s.apiextensions.CustomResource(
#     resource_name=pulumi_ceph_user_name,
#     api_version="ceph.rook.io/v1",
#     kind="CephObjectStoreUser",
#     metadata={
#         "name": pulumi_ceph_user_name,
#         "namespace": namespace.metadata["name"],
#     },
#     spec={
#         "store": object_store_name,
#         "displayName": "Pulumi User",
#         "capabilities": {
#             "user": "*",
#             "bucket": "*",
#         },
#     }
# )

# # TODO: Wait for user to be created
# pulumi_user_secret = k8s.core.v1.Secret.get(
#     resource_name=f"{pulumi_ceph_user_name}-secret",
#     id=f"{config.ceph_ns_name}/rook-ceph-object-user-{object_store_name}-{pulumi_ceph_user_name}",
#     opts=pulumi.ResourceOptions(depends_on=[pulumi_ceph_user]),
# )

# ceph_provider = aws.Provider(
#     resource_name="ceph-provider",
#     region=region_name,
#     s3_use_path_style=True,
#     endpoints=[
#         aws.ProviderEndpointArgs(
#             s3=f"https://{config.ceph_rgw_hostname}",
#         )
#     ],
#     custom_ca_bundle=config.root_ca_path,
#     skip_credentials_validation=True,
#     skip_requesting_account_id=True,
#     skip_region_validation=True,
#     skip_metadata_api_check=True,
#     access_key=pulumi_user_secret.data.apply(lambda data: base64.b64decode(data["AccessKey"]).decode("utf-8")),
#     secret_key=pulumi_user_secret.data.apply(lambda data: base64.b64decode(data["SecretKey"]).decode("utf-8")),
# )
