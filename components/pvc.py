
from pathlib import Path

import pulumi_kubernetes as kubernetes


def create_pvc(namespace_name: str, 
               volume_size: str,
               storage_class_name: str,
               pvc_name: str,
               local_persistence_dir: str | None = None,
               pv_name: str | None = None,
               policy: str = "Retain"):
    """
    Function resposible for creating PVC for resources which data should remain even if the resource is deleted.
    For local testing like on k3s it is responsible to create proper PV as well.
    """

    # Create PV in case of using local storage - done for k3s tests
    # For production there should be csi responsible for creating pv based on pvc below
    if local_persistence_dir:
        if not pv_name:
            raise ValueError("pv_name must be provided when using local_persistence_dir")
        Path(local_persistence_dir).mkdir(parents=True, exist_ok=True)
        pv = kubernetes.core.v1.PersistentVolume(
            pv_name,
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=pv_name,
                namespace=namespace_name,
            ),
            spec=kubernetes.core.v1.PersistentVolumeSpecArgs(
                capacity={"storage": volume_size},
                access_modes=["ReadWriteOnce"],
                persistent_volume_reclaim_policy=policy,
                storage_class_name=storage_class_name,
                host_path=kubernetes.core.v1.HostPathVolumeSourceArgs(
                    path=local_persistence_dir,
                ),
            ),
        )


    pvc = kubernetes.core.v1.PersistentVolumeClaim(
        pvc_name,
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name=pvc_name,
            namespace=namespace_name,
        ),
        spec=kubernetes.core.v1.PersistentVolumeClaimSpecArgs(
            access_modes=["ReadWriteOnce"],
            resources=kubernetes.core.v1.ResourceRequirementsArgs(
                requests={"storage": volume_size},
            ),
            storage_class_name=storage_class_name,
            volume_name=pv.metadata["name"] if local_persistence_dir else None,
        ),
    )

    return pvc