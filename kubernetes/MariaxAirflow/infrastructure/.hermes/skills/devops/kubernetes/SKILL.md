---
name: kubernetes
description: Kubernetes workload deployment and troubleshooting — Bitnami chart pitfalls (image override, secret key naming, post-rebrand defaults), StatefulSet recovery from stuck rollouts, ConfigMap/Secret wiring, common diagnostic commands. Load when working with k8s manifests, Helm charts (especially Bitnami), StatefulSets, Pods stuck in CrashLoopBackOff, image/registry issues, or k8s training/evaluation exercises.
---

# Kubernetes

Class-level umbrella for Kubernetes work. Triggers on:

- Helm install/upgrade of common apps (MariaDB, MySQL, PostgreSQL, Airflow, Redis, …)
- StatefulSet / Deployment / Pod troubleshooting (CrashLoopBackOff, Init errors, ImagePullBackOff)
- ConfigMap / Secret wiring into Pods
- Image, tag, and registry issues
- "Helm release won't upgrade" / stuck rollouts
- k8s training or evaluation exercises

## Bitnami chart pitfalls

Bitnami charts (mariadb, mysql, postgresql, redis, airflow, …) are widely used but have a few sharp edges.

### 1. Don't substitute the image

The chart's init containers (e.g. `preserve-logs-symlinks`) expect Bitnami's filesystem layout: `/opt/bitnami/scripts/libfs.sh`, `/opt/bitnami/<app>/logs` symlinks, etc. If you override `image.repository` to use the upstream Docker image (e.g. `mariadb` instead of `bitnami/mariadb`), the init container crashes immediately with:

```
/bin/bash: line 2: /opt/bitnami/scripts/libfs.sh: No such file or directory
```

→ Either remove the `image:` override entirely (let the chart pick the default), or use the Bitnami-built image (`bitnami/mariadb:10.x`).

### 2. `auth.existingSecret` key naming

`auth.rootPasswordKey: "password"` is NOT respected by the chart's `templates/secrets.yaml` validation template. The chart requires the secret to contain a key literally named `mariadb-root-password`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mariadb-root-password
type: Opaque
data:
  mariadb-root-password: <base64>   # NOT "password"
```

If the key is wrong, `helm install` errors with:

```
PASSWORDS ERROR: The secret "mariadb-root-password" does not contain the key "mariadb-root-password"
```

### 3. Chart 26.x+ rebrand and rolling tags

Since chart 26.x, Bitnami defaults to `registry-1.docker.io/bitnami/<app>:latest`. You'll see "Rolling tag detected" warnings on every install/upgrade. Warnings only, not errors — but pin a tag for production. To pin a Bitnami image explicitly:

```yaml
image:
  registry: registry-1.docker.io
  repository: bitnami/mariadb
  tag: "10.11"
```

### 4. Bitnami MariaDB auth model — `--skip-networking`, `unix_socket` plugin, non-standard socket path

Stand-alone (non-replication) Bitnami MariaDB launches mariadbd with `--skip-networking` and creates **two distinct `root` accounts**:

- `root@localhost` — no password, plugin `unix_socket`, only usable via the Unix socket at `/opt/bitnami/mariadb/tmp/mysql.sock` (NOT `/tmp/mysql.sock`).
- `root@'%'` — with the secret password, plugin `mysql_native_password`, only reachable via TCP — which is not listening in stand-alone mode.

The password is injected via the file `/opt/bitnami/mariadb/secrets/mariadb-root-password` (env `MARIADB_ROOT_PASSWORD_FILE`); the `MARIADB_ROOT_PASSWORD` env var is NOT set inside the container.

**Consequence**: `mysql -uroot -p"$VAR"` from inside the pod always fails with `Access denied for user 'root'@'localhost'`, and the liveness probe hits the same wall → pod restart loop (exit 137). The ConfigMap-injected my.cnf is still applied (visible via `SHOW VARIABLES`), so the database is actually working — the auth path is just non-obvious.

**Verification command** (works without TCP):

```bash
kubectl exec -n <ns> <pod> -- \
  /opt/bitnami/mariadb/bin/mariadb \
  --socket=/opt/bitnami/mariadb/tmp/mysql.sock -uroot \
  -e "SHOW VARIABLES LIKE 'max_allowed_packet'; SHOW DATABASES;"
```

For full details and TCP-access workarounds (replication mode or `primary.extraFlags`), see `references/bitnami-chart-pitfalls.md` Pitfall 6.

## Stuck rollout recovery (Helm + StatefulSet)

If a StatefulSet pod is stuck in `CrashLoopBackOff` and never becomes Ready, `helm upgrade` cannot progress the rollout — Helm waits for the existing pod to be replaced via the StatefulSet controller, which won't happen until the pod is Ready.

**Symptom**: `helm get manifest` shows the new image, but `kubectl get pod -o jsonpath='{.spec.containers[0].image}'` shows the old image. The release is "deployed" but the pods are unchanged.

**Fix**:

```bash
helm uninstall <release> -n <ns>
helm upgrade --install <release> bitnami/<chart> -f values.yaml -n <ns>
```

`helm uninstall` removes the StatefulSet and its pods. Manually-created Secrets are NOT touched by Helm, so they survive. Always verify with `kubectl get all -n <ns>` before re-installing.

## Diagnostic commands

```bash
# What does Helm think it deployed?
helm get manifest <release> -n <ns> | grep -A 1 "image:"
helm get values <release> -n <ns>

# What is the pod actually running?
kubectl get pod <pod> -n <ns> -o jsonpath='{.spec.containers[0].image}'
kubectl get pod <pod> -n <ns> -o jsonpath='{.spec.initContainers[0].image}'

# Why is the init container crashing?
kubectl logs <pod> -n <ns> -c <init-container-name> --previous

# Why is the liveness/readiness probe failing?
kubectl describe pod <pod> -n <ns> | grep -A 5 "Liveness\|Readiness"
kubectl get events --sort-by=.lastTimestamp -n <ns> | grep -i "probe\|killing"

# Rollout state
kubectl rollout status sts/<release> -n <ns>

# Verify Secret keys are what the chart expects
kubectl get secret -n <ns> <secret-name> -o jsonpath='{.data}'

# What ports is the container actually listening on?
kubectl exec <pod> -n <ns> -- ss -tlnp   # may need: apt-get install iproute2

# Clean slate (preserves manually-created Secrets)
helm uninstall <release> -n <ns>
kubectl get all -n <ns>
```


## Database Connectivity & Service Patterns

### Headless Services for Databases
When deploying stateful databases (MariaDB, MySQL, PostgreSQL), using a standard ClusterIP Service as a load balancer can lead to `Connection Refused (Error 2002)` or routing errors if the client needs to target a specific instance (e.g., the Master).

**The Solution: Headless Service (`clusterIP: None`)**
A Headless Service does not provide a single virtual IP. Instead, it allows the DNS to return the direct IP addresses of all pods in the set. This enables stable, predictable pod-level DNS names.

**DNS Pattern:**
`<pod-name>.<service-name>.<namespace>.svc.cluster.local`
Example: `mariadb-0.mariadb.airflow.svc.cluster.local`

**Implementation:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mariadb
spec:
  clusterIP: None # Headless
  selector:
    app: mariadb
  ports:
    - port: 3306
      targetPort: 3306
```

### Common Pitfalls in Manual StatefulSet Construction
- **Persistence:** Ensure `volumeClaimTemplates` is used instead of `volumes` with `emptyDir` to prevent data loss on pod restart.
- **Config Paths:** MySQL/MariaDB configuration files must be mounted to the exact expected path (e.g., `/etc/mysql/conf.d`) to be active.
- **Resource Limits:** Always define `requests` and `limits` for databases to avoid `OOMKilled` events during heavy migrations or Airflow initialization.


| STATUS | Likely cause | First thing to check |
|---|---|---|
| `Init:CrashLoopBackOff` | Init container failing | `kubectl logs <pod> -c <init> --previous` |
| `ImagePullBackOff` | Wrong image / registry / tag | `kubectl describe pod <pod>` Events |
| `Pending` | No node can schedule it (resources, taints, affinity) | `kubectl describe pod <pod>` Events |
| `Running` but not Ready | Readiness probe failing | `kubectl describe pod <pod>` Probes section |
| `Running`, restarts climbing, liveness probe errors with `Access denied` | DB auth mismatch (Bitnami-specific — see §4) | `kubectl exec` into pod, check users with socket auth |
| Helm says deployed, pods unchanged | Stuck rollout (see above) | `helm uninstall` + reinstall |

## See also

- `references/bitnami-chart-pitfalls.md` — error transcripts and reproduction recipes from real sessions
