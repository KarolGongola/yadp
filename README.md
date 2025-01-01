# Yet Another Data Platform
Kubernetes based data platform built from open source components. The idea is to build data platform which uses only basic functionalities from provider like s3, k8s, storageclass. With this assumption it could be running at any cloud (not only 3 largest) as well as at on-prem kubernetes.

In this repo you can see how to run it at local kubernetes (k3s) and at my hybrid homelab kubernetes (OCI + local VMs). My homelab setup you can see (with guest permissions) at [yadp.xyz](https://yadp.xyz)

Below I will describe how I have prepared my setup. It is not generic instruction, so you can modify whatever you wish or replicaty my approach.

## Prerequisities

### Common
* Linux terminal. I am using Ubuntu for running pulumi commands.
* Kubernetes with credentials saved to proper contexts in file which path is in `KUBECONFIG`. In my case `local` for local dev k3s k8s and and `eagle` for homelab k8s.
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
* Ability to create LoadBalancer service. E.g. installed metallb.

### For local dev k8s
* To mimic DNS server locally, put all hostnames in `/etc/hosts` like this:
    ```bash
    YOUR_IP_ADDRESS    trino.k3s.localhost
    YOUR_IP_ADDRESS    polaris.k3s.localhost
    YOUR_IP_ADDRESS    keycloak.k3s.localhost
    ...
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
    * Create persistence dir for some PVCs:
        ```bash
        mkdir -p ~/yadp_k3s_persistence_dir
        ```

## Create or update platform setup
* When starting new terminal, run init script to use local backend file
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
