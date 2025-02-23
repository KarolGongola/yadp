# Yet Another Data Platform
Kubernetes based data platform built from open source components.

In this repo you can see how to run it at local kubernetes (k3s) and at my hybrid homelab kubernetes (OCI + local VMs). My homelab setup you can see (with guest permissions) at [https://yadp.xyz](https://yadp.xyz)

## Requirements
* kubernetes (min 8 cores, 32GB memory)
* raw disks (min 3 disks or partitions without filesystem) - [more details](https://rook.io/docs/rook/v1.10/Getting-Started/Prerequisites/prerequisites/#ceph-prerequisites)
* git server (e.g. for Airflow DAGs)

## Components

### For now it includes:
* Pulumi -> Apache 2.0
* Cert Manager -> Apache 2.0
* Ingress Nginx -> Apache 2.0
* Ceph+Rook -> LGPL+Apache 2.0
* Keycloak -> Apache 2.0
* Trino -> Apache 2.0
* KEDA -> Apache 2.0
* Airflow -> Apache 2.0
* Prometheus -> Apache 2.0
* Grafana -> AGPLv3
### Planned:
* Apache Superset -> Apache 2.0
* DataHub -> Apache 2.0
* Kafka -> Apache 2.0
* VS Code Server -> MIT
* Spark -> Apache 2.0
* Apache Unicorn -> Apache 2.0
* Flink -> Apache 2.0
* Fluentd -> Apache 2.0
* Starrocks -> Apache 2.0
### To consider:
* Apache Solr -> Apache 2.0
* Apache Polaris -> Apache 2.0
* Lakekeeper -> Apache 2.0
* Velero -> Apache 2.0
* Gitlab -> MIT
* artifactory

## Prerequisities

### Common
* Linux terminal. I am using Ubuntu for running pulumi commands.
* Kubernetes with credentials saved to proper contexts in file which path is in `KUBECONFIG`. In my case `local` for local dev k3s k8s and and `eagle` for homelab k8s.
* pulumi installed -> https://www.pulumi.com/docs/iac/download-install/
* Reuse existing or create new pulumi stacks and configure them to use proper kubernetes context:
    ```bash
    pulumi stack select homelab
    pulumi config set kubernetes:context eagle
    pulumi stack select local
    pulumi config set kubernetes:context local
    ```
* Because I am not using neither pulumi cloud nor cloud encryption provider (like KMS), it is not safe to use `pulumi --secret`. I have decided to keep all initial passwords in env variables. So we need to set them in secure place and activate like:
    ```bash
    source ~/.yadp-secrets.sh
    ```
    Where content of .yadp-secrets.sh could be like:
    ```bash
    export LOCAL_KEYCLOAK_ADMIN_PASSWORD="XYZ"
    export HOMELAB_KEYCLOAK_ADMIN_PASSWORD="XYZ"
    ...
    ```

### For homelab k8s
* Domain with proper DNS records (In my case at godaddy.com)
* ClusterIssuer with letsencrypt ACME in `cert-manager` namespace.
* Make sure that traffic from domain (`https://yadp.xyz`) will be routed to homelab k8s nginx ingress controller
* Prepare storageclass for PVCs. I have truenas core server connected to k8s with [democratic-csi](https://github.com/democratic-csi/democratic-csi)
* Ability to create LoadBalancer service. E.g. installed metallb with ip pool created.

### For local dev k8s
* Install k3s
    ```bash
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server" K3S_KUBECONFIG_MODE="644" sh -s - --disable=traefik
    ```
* To mimic DNS server locally, put following line in `/etc/hosts`:
    ```bash
    YOUR_IP_ADDRESS(non localhost)    *.yadp.localhost
    YOUR_IP_ADDRESS(non localhost)    keycloak.yadp.localhost
    ```
* Pass your loacal /etc/hosts to coredens (to let applications inside k8s to resolve your locally defined hostnames)
    * Mount /etc/hosts to coredns pod
        * Edit Coredns deployment
            ```bash
            kubectl -n kube-system edit deployment coredns
            ```
        * Add volume
            ```yml
            volumes:
                - hostPath:
                    path: /etc/hosts
                    type: File
                  name: etc-hosts
            ```
        * Add volume mount
            ```yml
            volumeMounts:
                - mountPath: /etc/hosts
                  name: etc-hosts
                  readOnly: true
            ```
    * Configure coredns to use /etc/hosts
        * Edit coredns configmap
            ```bash
            kubectl edit configmap coredns -n kube-system
            ```
        * Replace existing hosts section with new one
            ```
            hosts /etc/hosts {
              ttl 60
              reload 15s
              fallthrough
            }
            ```
    * Create root CA and add it to linux trusted certs and manually to chrome (Settings -> Privacy and security -> Security -> Manage certificates -> Authorities)
        ```bash
        mkdir ~/yadp-certs
        openssl genrsa -out ~/yadp-certs/rootCA.key 2048
        openssl req -x509 -new -nodes -key ~/yadp-certs/rootCA.key -sha256 -days 1024 -out ~/yadp-certs/rootCA.crt
        sudo cp ~/yadp-certs/rootCA.crt /usr/local/share/ca-certificates/yadp-rootCA.crt
        sudo update-ca-certificates
        ```
    * Add root ca to local k3s
        ```bash
        kubectl config use-context local
        kubectl create ns cert-manager
        kubectl apply -f - <<EOF
        apiVersion: v1
        kind: Secret
        metadata:
          name: root-ca
          namespace: cert-manager
        type: kubernetes.io/tls
        data:
          tls.crt: $(cat ~/yadp-certs/rootCA.crt | base64 | tr -d '\n')
          tls.key: $(cat ~/yadp-certs/rootCA.key | base64 | tr -d '\n')
        EOF

        ```

## Create or update platform setup
* When starting new terminal, run init script to use local backend file and to load secrets as env variables.
    ```bash
    source ./init-pulumi.sh
    ```
* Select proper pulumi stack (destinantion kubernetes cluster) and double check the chosen one, e.g:
    ```bash
    pulumi stack select local
    pulumi stack ls
    ```
* Create or update platform
    ```bash
    pulumi up
    ```
* Terminal command to print all resource URNs:
    ```bash
    pulumi stack --show-urns
    ```
* Terminal command to print all resources from a namespace:
    ```bash
    kubectl get all -n <namespace>
    ```
