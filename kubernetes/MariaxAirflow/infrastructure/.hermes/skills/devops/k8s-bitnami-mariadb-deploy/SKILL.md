---
name: k8s-bitnami-mariadb-deploy
description: Deployment and troubleshooting of MariaDB using the Bitnami Helm chart.
category: devops
---

# Kubernetes Bitnami MariaDB Deployment & Troubleshooting

This skill covers the deployment of MariaDB using the Bitnami Helm chart, focusing on common pitfalls related to secrets management, persistence, and connectivity.

## Deployment Workflow
1. **Namespace Setup**: Always ensure the namespace is created and targets are applied specifically to it (`-n <namespace>`).
2. **Secret Management**: 
    - Define secrets for root and user passwords before installation.
    - Ensure the secret name matches the `existingSecret` value in `values.yaml`.
    - The key inside the secret must be named `password` for the chart to recognize it.
3. **Helm Installation**: 
    - Use `helm install` or `helm upgrade --install`.
    - Use a `values.yaml` file to configure `auth.existingSecret` and `primary.configuration` (e.g., `max_allowed_packet`).

## Common Pitfalls & Fixes

### 1. The "Persisted Data" Conflict (Credential Mismatch)
**Symptom**: Pod restarts in a loop (CrashLoopBackOff) or refuses connection after changing secrets.
**Cause**: Bitnami MariaDB initializes the DB on the first boot. If a PersistentVolumeClaim (PVC) exists, the server uses the password stored on disk, ignoring new secrets provided via Helm.
**Fix**: 
- `helm uninstall <release>`
- `kubectl delete pvc -l app.kubernetes.io/instance=<release> -n <namespace>`
- Re-install. This forces a fresh initialization with the new secrets.

### 2. Connection Error 2002 (HY000) / 115
**Symptom**: `Can't connect to server on 'mariadb.mariadb.svc.cluster.local'`.
**Diagnosis**:
- Check if Pod is `Ready 1/1`. If `0/1`, the Readiness probe is failing.
- Verify endpoints: `kubectl get endpoints -n <namespace>`. If empty, the service is not routing traffic.
- Check for "Running" but unstable pods (High Restart count).

### 3. SSL/TLS Handshake Failures
**Symptom**: `ERROR 2026 (HY000): TLS/SSL error: self-signed certificate`.
**Fix**: Add the `--skip-ssl` or `--ssl=OFF` flag to the `mariadb` / `mysql` client command.

### 4. Shell Variable Interpretation
**Symptom**: Passwords containing `$` or `!` cause shell errors (`event not found` or empty variables).
**Fix**: Wrap passwords in **single quotes** (`'password'`) to prevent Bash from interpreting special characters.

## Verification Procedure
1. **Internal Pod Check**: `kubectl exec -it <pod> -n <ns> -- netstat -tulpn | grep 3306` (Verify port is open).
2. **Client Test**: 
   - Launch client: `kubectl run mariadb-client --rm --tty -i --restart='Never' --image registry-1.docker.io/bitnami/mariadb:latest -n <ns> --command -- bash`
   - Connect: `mariadb -h <service-dns> -u root -p'password' --skip-ssl -e "SELECT 1;"`
