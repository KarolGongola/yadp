from pathlib import Path

import pulumi
import pulumi_kubernetes as kubernetes

from config import config


def create_pvc(
    namespace_name: str,
    volume_size: str,
    storage_class_name: str,
    pvc_name: str,
    persistence_dir: str | None = None,
    pv_name: str | None = None,
    policy: str = "Retain",
    access_modes: list[str] = None,
) -> kubernetes.core.v1.PersistentVolumeClaim:
    """
    Function resposible for creating PVC for resources which data should retain even if the resource is deleted.
    For local testing like on k3s it is responsible to create proper PV as well.
    """

    # Create PV in case of using local storage - done for k3s tests
    # For production there should be csi responsible for creating pv based on pvc below
    if config.local_persistence_dir:
        local_persistence_path = str(Path(config.local_persistence_dir) / persistence_dir)
        if not pv_name:
            raise ValueError("pv_name must be provided when using local_persistence_dir")
        Path(local_persistence_path).mkdir(parents=True, exist_ok=True)
        pv = kubernetes.core.v1.PersistentVolume(
            pv_name,
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=pv_name,
                namespace=namespace_name,
            ),
            spec=kubernetes.core.v1.PersistentVolumeSpecArgs(
                capacity={"storage": volume_size},
                access_modes=access_modes or ["ReadWriteOnce"],
                persistent_volume_reclaim_policy=policy,
                storage_class_name=storage_class_name,
                host_path=kubernetes.core.v1.HostPathVolumeSourceArgs(
                    path=local_persistence_path,
                ),
            ),
        )

    return kubernetes.core.v1.PersistentVolumeClaim(
        pvc_name,
        opts=pulumi.ResourceOptions(protect=config.protect_persisted_resources),
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name=pvc_name,
            namespace=namespace_name,
        ),
        spec=kubernetes.core.v1.PersistentVolumeClaimSpecArgs(
            access_modes=access_modes or ["ReadWriteOnce"],
            resources=kubernetes.core.v1.ResourceRequirementsArgs(
                requests={"storage": volume_size},
            ),
            storage_class_name=storage_class_name,
            volume_name=pv.metadata["name"] if config.local_persistence_dir else None,
        ),
    )
