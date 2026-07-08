---
name: kubernetes-mariadb-airflow-deploy
description: Orchestrating MariaDB and Airflow deployments on Kubernetes, focusing on persistence and configuration injection.
---

# Kubernetes MariaDB & Airflow Deployment

## Workflow
1. **Infrastructure Base**: Deploy Secrets, PVs, and PVCs first.
2. **Configuration Injection**: Encapsulate native config files (e.g., `.cnf`) into `ConfigMaps` before deploying the server.
3. **StatefulSet Deployment**: Deploy MariaDB using a StatefulSet for stable identity and persistence.
4. **Orchestrator Deployment**: Deploy Airflow (typically via Helm) once the database is `Running`.

## Critical Pitfalls & Fixes

### 1. The `.cnf` Validation Error
- **Symptom**: `kubectl apply -f mysqld.cnf` returns `invalid object to validate`.
- **Root Cause**: `kubectl apply` expects a Kubernetes manifest (YAML), not a native config file.
- **Fix**: Create a ConfigMap from the file: 
  `kubectl create configmap <name> --from-file=<key>=<path>`

### 2. The "Pending" Pod / Unbound PVC
- **Symptom**: MariaDB pod stays in `Pending` with `unbound immediate PersistentVolumeClaims`.
- **Root Cause**: StatefulSets use `volumeClaimTemplates` to create dynamic PVCs (e.g., `data-mariadb-0`). If a manual PVC (e.g., `mariadb-pvc`) was created, the StatefulSet ignores it and tries to create its own, which fails if no matching PV is available.
- **Fix**: 
    - Remove `volumeClaimTemplates` from the StatefulSet YAML.
    - Add the specific PVC to the `volumes` section:
      ```yaml
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: mariadb-pvc
      ```

### 3. Permission Denied on Volumes
- **Symptom**: Pod enters `CrashLoopBackOff` with `Permission Denied` in logs.
- **Root Cause**: MariaDB runs as UID 999. Host directories created by root are inaccessible.
- **Fix**: `sudo chmod 777 /mnt/mariadb_data` (Lab/Test) or `sudo chown -R 999:999 /mnt/mariadb_data` (Prod).

### 4. Connection Refused (External Access)
- **Symptom**: `ERR_CONNECTION_REFUSED` when accessing the Web UI via Public IP.
- **Root Cause**: Services default to `ClusterIP` (internal only).
- **Fix**: 
    - Temporary: `kubectl port-forward svc/<service-name> 8080:8080 -n <namespace>`
    - Permanent: Change service type to `LoadBalancer` via `kubectl patch`.

## Verification Checklist
- [ ] Secrets created?
- [ ] PV/PVC Bound?
- [ ] ConfigMap created?
- [ ] Pod Status == Running?
- [ ] Port-forward active?
