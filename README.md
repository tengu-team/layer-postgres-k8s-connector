# Postgres-K8S connector

This charm installs a subordinate on all the kubernes workers and will whitelist all the worker ip's in the postgres config file.
This charm also needs a relation with the kubernetes deployer to create the right secret and configmap. The charm will then create a new database that can be used for the provided namespace
from the kubernetes deployer and by using k8s secret and configmap, all deployments will be able able to use the DB on postgres.

## Configs

It has the same 3 config values as the SSL-termination-proxy:

- **`database`**  the name of the database that should be created for Postgres

## How to deploy


```bash
# make sure you have a running k8s cluster
juju deploy cs:~tengu-team/kubernetes-deployer 
juju deploy postgres-k8s-connector 
# Configure the connector
juju config postgres-k8s-connector database="keycloak"
# add the required relations
juju add-relation postgres-k8s-connector kubernetes-deployer 
juju add-relation postgres-k8s-connector:postgres postgresql:db
juju add-relation postgres-k8s-connector:kube-host kubernetes-worker
```

## Authors
 - Sebastien Pattyn <sebastien.pattyn@tengu.io>
