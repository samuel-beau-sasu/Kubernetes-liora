# Bitnami chart pitfalls — session transcripts

Concrete error transcripts collected from real sessions. Use alongside the
parent skill's diagnostic commands.

## Pitfall 1: image substitution breaks init containers

**Setup**: `mariadb-values.yaml` contained:
```yaml
image:
  registry: docker.io
  repository: mariadb
  tag: "10.4"
```
(Upstream image instead of Bitnami-built.)

**Symptom**: Pod stuck in `Init:CrashLoopBackOff`.

**Log from init container `preserve-logs-symlinks`**:
```
/bin/bash: line 2: /opt/bitnami/scripts/libfs.sh: No such file or directory
```

**Why**: Bitnami's init containers expect the Bitnami filesystem layout.
Upstream `mariadb:10.4` does not have `/opt/bitnami/scripts/libfs.sh`.

**Fix**: Remove the `image:` override entirely and let the chart use its
default `bitnami/mariadb:<ver>` image. Then `helm uninstall` and reinstall
(see Pitfall 4 — the pod will not auto-upgrade).

**Bitnami warning you may have ignored**:
```
⚠ SECURITY WARNING: Original containers have been substituted.
Substituted images detected:
  - docker.io/mariadb:10.4
```

---

## Pitfall 2: Secret key naming

**Setup**: `secret-root-password.yaml` contained:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mariadb-root-password
type: Opaque
data:
  password: RGF0YXNjaWVudGVzdDIwMjNAISE=
```

**`mariadb-values.yaml`**:
```yaml
auth:
  existingSecret: "mariadb-root-password"
  rootPasswordKey: "password"
```

**Symptom**:
```
Release "mariadb" does not exist. Installing it now.
Error: execution error at (mariadb/templates/secrets.yaml:8:21):
PASSWORDS ERROR: The secret "mariadb-root-password" does not contain the
key "mariadb-root-password"
```

**Why**: The chart's `templates/secrets.yaml` validation template checks for
a key literally named `mariadb-root-password` regardless of what
`rootPasswordKey` says.

**Fix**: Rename the data key to match:
```yaml
data:
  mariadb-root-password: RGF0YXNjaWVudGVzdDIwMjNAISE=
```

---

## Pitfall 3: Two-secrets pattern for user + root

When using `auth.existingSecret` for the root password AND a separate
`auth.customPasswordFilesSecret` for an app user, the secret containing the
root password must be the one whose key is named `mariadb-root-password`
(Pitfall 2). The user secret can keep its own keys (`MARIADB_USER`,
`MARIADB_PASSWORD`):

```yaml
# secret-root-password.yaml  — KEY MUST BE mariadb-root-password
apiVersion: v1
kind: Secret
metadata:
  name: mariadb-root-password
type: Opaque
data:
  mariadb-root-password: <base64>

# secret-mariadb-user.yaml    — keys can be MARIADB_USER / MARIADB_PASSWORD
apiVersion: v1
kind: Secret
metadata:
  name: mariadb-user
type: Opaque
data:
  MARIADB_USER: <base64>
  MARIADB_PASSWORD: <base64>
```

---

## Pitfall 4: Helm release "deployed" but pod unchanged

**Symptom**: After fixing the image and running `helm upgrade --install`,
`helm get manifest` shows the new image (e.g. `bitnami/mariadb:latest`)
but `kubectl get pod -o jsonpath='{.spec.containers[0].image}'` still
shows the old image (e.g. `docker.io/mariadb:10.4`).

**Why**: The pod is in `Init:CrashLoopBackOff`, never becomes Ready, so the
StatefulSet controller can't roll it forward. `helm upgrade` succeeds
against the API but the pod stays put.

**Fix**:
```bash
helm uninstall mariadb -n mariadb
# Manually-created Secrets (mariadb-root-password, mariadb-user) survive.
kubectl get all -n mariadb    # verify only your secrets remain
helm upgrade --install mariadb bitnami/mariadb -f mariadb-values.yaml -n mariadb
```

---

## Pitfall 5: `helm get manifest` vs actual pod image

When debugging, ALWAYS check both:

```bash
# What the release spec says
helm get manifest mariadb -n mariadb | grep -A 1 "image:"

# What the pod actually runs
kubectl get pod mariadb-0 -n mariadb -o jsonpath='{.spec.containers[0].image}'
kubectl get pod mariadb-0 -n mariadb -o jsonpath='{.spec.initContainers[0].image}'
```

If they disagree, the pod is stale (see Pitfall 4).

---

## Pitfall 6: Bitnami MariaDB auth model — `Access denied for user 'root'@'localhost'`

**Symptom** (after a clean install with `auth.existingSecret` and a working pod):

```bash
kubectl exec -it mariadb-0 -n mariadb -- /bin/sh
$ mysql -uroot -p${MARIADB_ROOT_PASSWORD} -e "SHOW VARIABLES LIKE 'max_allowed_packet';"
Enter password:
ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)
```

And `kubectl describe pod` shows the **liveness probe failing** in a loop, eventually causing `Container mariadb failed liveness probe, will be restarted` → pod restart loop.

**Why**: Bitnami MariaDB sets up two distinct `root` accounts (see
`/opt/bitnami/scripts/libmariadb.sh` line ~1028):

1. `root@localhost` — **no password**, authenticated via the `unix_socket`
   plugin. Only usable from inside the pod via the Unix socket, and only if
   the client process runs as the right UID.
2. `root@'%'` — **with the password** from your secret, via
   `mysql_native_password`. Only reachable over **TCP**.

Plus, the mariadbd process is launched with `--skip-networking` in
stand-alone (non-replication) mode. So:

- The default socket location is `/opt/bitnami/mariadb/tmp/mysql.sock`
  (NOT `/tmp/mysql.sock`).
- TCP 3306 is **not listening** at all. `ss -tlnp` returns empty.
- `MARIADB_ROOT_PASSWORD` env var is empty inside the container — Bitnami
  injects the password via the file
  `/opt/bitnami/mariadb/secrets/mariadb-root-password` and the env var
  `MARIADB_ROOT_PASSWORD_FILE` (visible in `kubectl describe pod`).

So three things go wrong at once when you try the obvious `mysql -uroot -p...`:

- `-p${MARIADB_ROOT_PASSWORD}` → empty password (env var unset) → server
  rejects because `root@localhost` is unix_socket plugin, not password.
- The shell defaults to socket `/tmp/mysql.sock` which doesn't exist →
  falls back to TCP `localhost` which is not listening → error 2002 / 115.
- Even with the right socket path, `root@localhost` ignores the password
  because the plugin is `unix_socket`.

**Fix — to verify MariaDB is working, use the socket as root with no password**:

```bash
kubectl exec -n mariadb mariadb-0 -- \
  /opt/bitnami/mariadb/bin/mariadb \
  --socket=/opt/bitnami/mariadb/tmp/mysql.sock \
  -uroot \
  -e "SELECT user, host FROM mysql.global_priv; SHOW VARIABLES LIKE 'max_allowed_packet'; SHOW DATABASES;"
```

(`mysql` works too but Bitnami prints a deprecation warning suggesting
`/opt/bitnami/mariadb/bin/mariadb`.)

**If you actually need TCP access** (e.g. from another pod, via the
service), you need to either:

- enable Bitnami replication mode (`architecture: replication`), which
  forces TCP listening; OR
- override the `my.cnf` via a ConfigMap to remove `--skip-networking` and
  explicitly `bind-address = 0.0.0.0`. Note that the chart's startup
  script appends `--skip-networking` from the CLI, so the ConfigMap alone
  may not be enough — you may need to remove it via `primary.extraFlags`
  or a custom entrypoint.

**To read the password from inside the pod** (for any in-pod tooling):

```bash
cat /opt/bitnami/mariadb/secrets/mariadb-root-password
```

Do NOT rely on `MARIADB_ROOT_PASSWORD` being exported — it isn't.

**Liveness/readiness probe also uses the same broken pattern**. The probe
script reads `MARIADB_ROOT_PASSWORD_FILE` correctly, but if your
`auth.existingSecret` setup was buggy on a first install and you re-installed
without wiping the data dir, MariaDB's internal user table may be
initialized with a different password than your secret. Symptom: probe
keeps failing with `Access denied`, kubelet kills the container
(SIGKILL = exit 137), pod restart loop. Fix: `helm uninstall` + reinstall
with `persistence.enabled: false` so the emptyDir gets recreated cleanly.

**Verification that ConfigMap-injected config worked** (the original
exercise's goal — `max_allowed_packet = 128M`):

```bash
kubectl exec -n mariadb mariadb-0 -- \
  /opt/bitnami/mariadb/bin/mariadb \
  --socket=/opt/bitnami/mariadb/tmp/mysql.sock -uroot \
  -e "SHOW VARIABLES LIKE 'max_allowed_packet';"
# Expected: max_allowed_packet  134217728   (128 MiB exactly)
```
