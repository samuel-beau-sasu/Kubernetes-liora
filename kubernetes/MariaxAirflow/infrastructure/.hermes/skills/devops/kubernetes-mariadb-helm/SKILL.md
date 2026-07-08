---
name: kubernetes-mariadb-helm
description: Deploying and troubleshooting Bitnami MariaDB on Kubernetes using Helm, focusing on secret management and network connectivity.
---

# MariaDB Helm Deployment (Bitnami)

This skill governs the deployment of MariaDB using the Bitnami Helm chart, specifically handling the transition from random credentials to custom secrets and optimizing database parameters.

## Core Workflow

### 1. Clean Installation
To avoid credential conflicts between the disk (PVC) and Kubernetes Secrets, always perform a clean wipe when changing authentication methods.
```bash
helm uninstall <release-name> -n <namespace>
kubectl delete pvc -l app.kubernetes.io/instance=<release-name> -n <namespace>
```

### 2. Custom Secret Integration
When using `existingSecret`, ensure the secret contains the key `password` (default for Bitnami) and is located in the same namespace as the release.
```bash
kubectl apply -f root-secret.yaml -n <namespace>
```

### 3. Deployment with Values
Use a `values.yaml` to link the secrets.
```yaml
auth:
  existingSecret: <secret-name>
  rootPasswordKey: password
```

## Troubleshooting & Pitfalls

### Connectivity Error 2002 (HY000) / (115)
If the pod is `Ready 1/1` but the client cannot connect:
- **Avoid `primary.configuration` for network settings**: Injecting `bind-address` or `skip-networking` via the `configuration` block can sometimes corrupt the `my.cnf` or cause the server to ignore network interfaces.
- **Verify Service/Endpoints**: Check `kubectl get endpoints -n <namespace>` to ensure the service is actually routing to the pod.

### The "Persisted Data" Trap
If logs show `Using persisted data`, MariaDB will **ignore** changes to `existingSecret` because the password is already written to the disk. 
- **Fix**: Delete the PVC and redeploy.

### SSL/TLS Errors
Bitnami MariaDB uses self-signed certificates by default. Clients will reject these unless configured otherwise.
- **Fix**: Add `--skip-ssl` or `--ssl=OFF` to the connection command.

## Advanced Configuration

### Modifying `max_allowed_packet`
Do NOT use the `configuration` block if it causes network issues. Instead, use `primary.extraFlags`. This passes the argument directly to the process and is more stable.

**Correct Syntax in values.yaml:**
```yaml
primary:
  extraFlags: "--max-allowed-packet=134217728" # Value in bytes (128M)
```

## Verification Suite
```bash
# Recover root password from secret
kubectl get secret <secret-name> -n <namespace> -o jsonpath="{.data.mariadb-root-password}" | base64 -d

# Test connection from client pod
mariadb -h <service-name>.<namespace>.svc.cluster.local -u root -p'<password>' --skip-ssl -e "SELECT 1;"
```
