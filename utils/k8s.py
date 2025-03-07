import base64
from functools import lru_cache
from pathlib import Path

import certifi
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


@lru_cache
def get_ca_bundle() -> str:
    """
    Return a CA bundle containing both the decoded root certificate
    and globally trusted root certificates from certifi.

    Returns:
        str: The combined CA bundle as a string
    """
    # Get the decoded root certificate
    root_cert = get_decoded_root_cert()

    # Get the globally trusted certificates from certifi
    with Path.open(certifi.where(), "r") as f:
        trusted_certs = f.read()

    # Combine the certificates
    return root_cert + "\n" + trusted_certs
