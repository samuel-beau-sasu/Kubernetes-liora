---
name: kubernetes-helm-bitnami-databases
description: Deploying and debugging stateful databases (MariaDB, MySQL, PostgreSQL, MongoDB, Redis) on Kubernetes via Bitnami Helm charts. Covers the recurring gotchas — secret key naming, init phase vs liveness probe races, the --skip-networking lifecycle, the two-tier auth model (unix_socket vs mysql_native_password), image-substitution pitfalls, and the CLI-args-over-my.cnf priority. Load when the user is working with a Bitnami database chart, has a StatefulSet pod stuck in CrashLoopBackOff, or asks about Bitnami-specific auth / network / secret behavior.
---

# Kubernetes + Bitnami database Helm charts

## When to load

- User is installing / upgrading a Bitnami database chart (`bitnami/mariadb`, `bitnami/mysql`, `bitnami/postgresql`, `bitnami/mongodb`, `bitnami/redis`, etc.)
- StatefulSet pod is in `Init:CrashLoopBackOff` or `CrashLoopBackOff` after a `helm install` that previously succeeded
- User has an `auth.existingSecret` (or equivalent) configured with a custom K8s Secret
- User asks: "why does `root@localhost` reject my password", "why can't I connect via the service", "why isn't port 3306/5432/27017 listening", "Access denied (using password: YES) — but the password is right"
- User added a setting to `my.cnf` / `postgresql.conf` and is asking why it didn't take effect
- User is working through a Kubernetes / data-platform training course that uses Bitnami charts as teaching material

## Standard debugging sequence

When a Bitnami database pod won't come up, won't accept connections, or auth fails, run these in order before guessing:

1. **Release state — did the values.yaml actually apply?**
   ```bash
   helm history <release> -n <ns>                  # confirm a new REVISION after your edit
   helm get values <release> -n <ns>               # shows USER-SUPPLIED VALUES
   helm get manifest <release> -n <ns> | grep -A1 "image:"   # confirms image override
   ```

2. **Pod + container state**
   ```bash
   kubectl get pods -n <ns> -l app.kubernetes.io/instance=<release>
   kubectl describe pod <pod> -n <ns>              # Events block shows probe failures, image pull errors, scheduling issues
   ```

3. **Logs by container** — Bitnami charts run multiple init containers + the main one. Try them all, both current and previous:
   ```bash
   kubectl logs <pod> -n <ns> -c <container>           # current
   kubectl logs <pod> -n <ns> -c <container> --previous  # last crashed instance
   ```
   Common container names: `preserve-logs-symlinks`, `init-config`, `init-checks`, `mariadb` / `mysql` / `postgresql`.

4. **Inside the pod** (once the main container is at least briefly running):
   ```bash
   kubectl exec -it <pod> -n <ns> -c <container> -- /bin/bash
   ps aux | grep -E "mariadbd|mysqld|postgres" | grep -v grep   # actual CLI flags the server was launched with
   ss -tlnp 2>/dev/null || netstat -tlnp                       # what's actually listening
   cat /opt/bitnami/mariadb/conf/my.cnf                          # what config the chart mounted
   cat /opt/bitnami/mariadb/secrets/*                            # what secrets the chart mounted
   ```

5. **Auth check (passwordless via socket)** — always works if init completed:
   ```bash
   kubectl exec <pod> -n <ns> -c <container> -- \
     /opt/bitnami/mariadb/bin/mariadb --socket=/opt/bitnami/mariadb/tmp/mysql.sock \
     -uroot -e "SELECT user, host FROM mysql.global_priv;"
   ```

## Workflow pitfall — when the user wants YOU to run multi-step fixes

When this skill's debugging path requires multiple destructive or stateful
steps (helm uninstall, helm upgrade, pod deletion, secret rewrite), **state
the plan and ask "lance la séquence ?" or equivalent before executing**.
The user working through Kubernetes training material prefers to delegate
execution when offered, and will say "lance-la" / "fais les étapes" / "exécute
pour moi" — they want to see real tool output, not a description of one.
The corollary: once they say "go", execute every step and report each result,
do not stop after a single command or a plan.

## The eight gotchas (memorize these)

### 1. Secret KEY naming, not secret NAMING
Bitnami charts look up secrets by **exact key name** in the secret's `data` section. The chart's docs imply that `auth.existingSecret: foo` is enough, but the chart's `templates/secrets.yaml` reads specific key names (e.g. `mariadb-root-password`, `mariadb-password`, `mariadb-user`). If your secret has the right NAME but the wrong KEY, the install fails with:
```
Error: execution error at (mariadb/templates/secrets.yaml:8:21):
PASSWORDS ERROR: The secret "X" does not contain the key "mariadb-root-password"
```
**Fix**: read `templates/secrets.yaml` in the chart to see exactly which keys it expects, and match them in your Secret's `data` block.

### 2. Image substitution breaks init containers
If you override `image.repository: mariadb` (Docker Hub upstream) instead of leaving the default `bitnami/mariadb`, the init containers crash with:
```
/bin/bash: /opt/bitnami/scripts/libfs.sh: No such file or directory
```
Bitnami's init containers depend on paths (`/opt/bitnami/scripts/libfs.sh`, `/opt/bitnami/mariadb/...`, `/opt/bitnami/scripts/libmariadb.sh`) that only exist in the Bitnami-built image. **Do not substitute the image** unless you also swap the chart for one designed for the upstream image. To use the chart's default image, just don't set `image:` in values.yaml at all (comment the block out, or set `image.tag` to the chart's recommended version if you need a specific one).

### 3. CLI args override my.cnf
MariaDB's flag resolution order: command-line args > `my.cnf`. Bitnami's entrypoint / `libmariadb.sh` launches `mariadbd` with explicit flags like `--skip-networking`, `--skip-slave-start`, `--log-error=...`, `--socket=...`. Setting these to `0` or to new values in `my.cnf` will NOT take effect — the args win.
- **Detection**: `ps aux | grep mariadbd` inside the pod shows the actual flags. If `--skip-networking` is there, your `skip-networking = 0` in my.cnf is being ignored.

### 4. Liveness probe can kill the init phase
Bitnami's default liveness probe (in chart 26.x) is roughly:
```bash
mariadb-admin status -uroot -p"$MARIADB_ROOT_PASSWORD_FILE_CONTENTS"
```
During the `Starting MariaDB in background` step of init, the server is in a state where `root@localhost` is set up with `unix_socket` auth, which **rejects password auth**. The probe fails repeatedly. After 3 failures (delay=120s, period=10s, failure=3), kubelet SIGKILLs the container (exit 137). The init never reaches "Stopping MariaDB in background" and never transitions to `run.sh`. The pod stays in `--skip-networking` mode forever and loops.

**Symptom**:
- `ps aux | grep mariadbd` shows `--skip-networking` flag in the args
- `ss -tlnp` shows no TCP listeners
- Pod in steady CrashLoopBackOff
- `kubectl describe pod` Events show: `Liveness probe failed: Access denied for user 'root'@localhost' (using password: YES)` followed by `Container mariadb failed liveness probe, will be restarted`

**Fix**: disable probes in values.yaml during the initial install, then re-enable them with a TCP-based probe once the install is validated:
```yaml
primary:
  livenessProbe:
    enabled: false
  readinessProbe:
    enabled: false
```

### 5. Two-tier auth model
Bitnami creates two distinct root accounts during init:
- `root@localhost` — plugin `unix_socket`, **no password required when connecting via the Unix socket** (the socket is at `/opt/bitnami/mariadb/tmp/mysql.sock`, not `/tmp/mysql.sock`)
- `root@%` (and `root@<pod-name>`, `root@127.0.0.1`, `root@::1`) — plugin `mysql_native_password`, **password required when connecting via TCP**

Implications:
- `kubectl exec … -- mysql -uroot` (no `-p`) works from inside the pod, no password needed — but ONLY if you specify the right socket (`--socket=/opt/bitnami/mariadb/tmp/mysql.sock`) or the mariadb client auto-discovers it
- `mysql -h mariadb.svc.cluster.local -uroot -p$PASS` requires the password to match what Bitnami stored
- `mysql -uroot -p$PASS` inside the pod (no `-h`) connects via the local socket → plugin `unix_socket` rejects the password → "Access denied (using password: YES)". The fact that this error mentions `(using password: YES)` is the giveaway that you're hitting the socket, not TCP.

### 6. The --skip-networking dance
`/opt/bitnami/scripts/libmariadb.sh` has a function `mariadb_start_bg` that launches `mariadbd` with `--skip-networking` so that init scripts can run in isolation (no external clients can connect mid-init). The `setup.sh` orchestrator is supposed to:
1. Launch in background with `--skip-networking`
2. Run init SQL (create users, schema, etc.)
3. Stop the background mariadbd
4. Launch `run.sh` in the foreground, **without** `--skip-networking`

If step 1→3 never completes (liveness probe killing the pod, init hanging on a missing file, etc.), the pod stays in `--skip-networking` mode indefinitely. Port 3306 never opens. The Kubernetes Service exists and points to the right port, but no backend listens, so `mysql -h svc.cluster.local` returns "Can't connect to server" (error 2002 / 115).

**Detection**: `ps aux | grep mariadbd` should NOT show `--skip-networking` once init is complete. If it does, init never finished.

### 7. `helm upgrade` doesn't auto-redeploy broken pods
`helm upgrade` updates the release's stored spec, but the kubelet won't replace a pod that's in CrashLoopBackOff — it keeps trying to restart the same broken pod. A successful `helm upgrade` (REVISION bumps, "Upgrade complete" message) does NOT mean the running pod reflects the new values. To get a clean re-deploy, uninstall and reinstall:
```bash
helm uninstall <release> -n <ns>   # removes StatefulSet, services, configmaps created by the chart
helm install <release> bitnami/<chart> -f values.yaml -n <ns>
```
This preserves manually-created K8s Secrets (the chart doesn't own them — `helm uninstall` only deletes resources with the chart's `app.kubernetes.io/managed-by: Helm` label).

### 8. `my.cnf not writable` warning
You'll see this in init logs:
```
WARN ==> The mariadb configuration file '/opt/bitnami/mariadb/conf/my.cnf' is not writable. Configurations based on environment variables will not be applied for this file.
```
This is informational — `primary.configuration` from values.yaml is still applied via a different mechanism (the chart mounts a tmpfs/CopyOnWrite version, or merges env-derived settings separately). Just don't try to edit my.cnf at runtime.

### 9. The Namespace mismatch pitfall
When creating K8s Secrets manually via `kubectl apply -f secret.yaml`, if the YAML does not explicitly define a `metadata.namespace`, the secret is created in the **current context's namespace** (usually `default`). If the Helm release is installed in a different namespace (e.g., `-n mariadb`), the chart will fail to find the secrets or create them using defaults, even if you used `auth.existingSecret`.
**Fix**: Always use the `-n <namespace>` flag during apply:
```bash
kubectl apply -f secret.yaml -n <namespace>
```
And verify their presence before deploying:
```bash
kubectl get secrets -n <namespace>
```

## Working values.yaml template

See `templates/mariadb-values-known-good.yaml` for a tested configuration covering: external secret injection, ConfigMap with `max_allowed_packet`, emptyDir storage, probes disabled as a workaround, and resource requests/limits.

## Reference

- `references/bitnami-mariadb-debug-walkthrough.md` — the full error chain from a real install attempt (wrong secret key → wrong image → probe-vs-init race → my.cnf overridden by args), with the exact `kubectl describe pod` / `ps aux` / `ss` outputs that pinpointed each root cause.
