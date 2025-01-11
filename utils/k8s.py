import base64
from functools import lru_cache

import kubernetes

from config import config


@lru_cache
def get_decoded_root_cert() -> str:
    kubernetes.config.load_kube_config(context=config.k8s_context)
    v1 = kubernetes.client.CoreV1Api()

    # Read the secret
    secret = v1.read_namespaced_secret(name=config.root_ca_secret_name, namespace=config.cert_manager_ns_name)
    encoded_root_cert = secret.data["tls.crt"]
    return base64.b64decode(encoded_root_cert).decode("utf-8")
