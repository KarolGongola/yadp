from dataclasses import dataclass, field
import os
from pathlib import Path
import pulumi


@dataclass(kw_only=True)
class Config:
    pulumi_config: pulumi.Config = field(default_factory=pulumi.Config)
    domain_name: str = None
    root_ca_secret_name: str = "root-ca"
    storage_class_name: str = None
    local_persistence_dir: str = None
    cert_manager_ns_name: str = "cert-manager"
    cert_manager_name: str = "cert-manager"
    cluster_issuer_name: str = "cluster-issuer"
    ingress_ns_name: str = "ingress-controller"
    ingress_controller_name: str = "nginx-ingress"
    keycloak_admin_login: str = "admin"
    keycloak_ns_name: str = "keycloak"
    keycloak_name: str = "keycloak"
    
    @property
    def keycloak_url(self):
        return f"keycloak.{self.domain_name}"
    

@dataclass(kw_only=True)
class LocalConfig(Config):
    domain_name: str = "k3s.localhost"
    storage_class_name: str = "local-path"
    local_persistence_dir: str = Path("~/yadp_k3s_persistence_dir").expanduser()
    
    @property
    def cluster_issuer_spec(self) -> dict:
        return {
            "ca": {
                "secretName": self.root_ca_secret_name,
            }
        }
    
    @property
    def keycloak_admin_password(self) -> str:
        return os.getenv("LOCAL_KEYCLOAK_ADMIN_PASSWORD")


@dataclass(kw_only=True)
class HomelabConfig(Config):
    domain_name: str = "yadp.xyz"
    storage_class_name: str = "freenas-iscsi-csi"
    cluster_issuer_spec: dict = field(default_factory=lambda: {
        "acme": {
            "server": "https://acme-v02.api.letsencrypt.org/directory",
            "email": "karol.gongola@gmail.com",
            "privateKeySecretRef": {
                "name": "letsencrypt-account-key",
            },
            "solvers": [
                {
                    "http01": {
                        "ingress": {
                            "class": "nginx",
                        }
                    }
                }
            ]
        }
    })

    @property
    def keycloak_admin_password(self) -> str:
        return os.getenv("HOMELAB_KEYCLOAK_ADMIN_PASSWORD")


pulumi_stack = pulumi.get_stack()
config = HomelabConfig() if pulumi_stack == "homelab" else LocalConfig()
