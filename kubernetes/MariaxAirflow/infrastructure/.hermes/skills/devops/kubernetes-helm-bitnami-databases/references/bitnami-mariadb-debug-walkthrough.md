# Bitnami MariaDB debug walkthrough — real session transcript

Captured from a Helm install of `bitnami/mariadb` chart 26.1.7 on a Datascientest
Kubernetes training cluster (1 node, namespace `mariadb`, Linux/AWS).

## Goal
Deploy a single MariaDB primary with:
- root password sourced from a pre-existing K8s Secret `mariadb-root-password`
- a separate K8s Secret `mariadb-user` for an application user
- `max_allowed_packet = 128M` in my.cnf
- emptyDir storage (no PVC)
- reachable so we can run `mysql` from inside the pod

## Error chain (in order encountered)

### Error 1 — secret key mismatch

```
Error: execution error at (mariadb/templates/secrets.yaml:8:21):
PASSWORDS ERROR: The secret "mariadb-root-password" does not contain the key "mariadb-root-password"
```

**Root cause**: Secret `mariadb-root-password` had `data.password: ...` but the
chart's `templates/secrets.yaml` reads the key named `mariadb-root-password`.
**Fix**: renamed the key in the Secret to `mariadb-root-password`.

### Error 2 — Init:CrashLoopBackOff, libfs.sh missing

```
/bin/bash: line 2: /opt/bitnami/scripts/libfs.sh: No such file or directory
```

**Root cause**: previous `helm install` had overridden `image.repository: mariadb`
(Docker Hub upstream) instead of using the chart's default `bitnami/mariadb`.
Upstream image lacks `/opt/bitnami/scripts/...` entirely.
**Fix**: removed the `image:` block from values.yaml (commented it out).

### Error 3 — Helm doesn't reset a CrashLoopBackOff pod on upgrade

After fix #2, `helm upgrade` returned "Happy Helming! ... Upgrade complete" but
the pod was still running with the OLD image (`docker.io/mariadb:10.4`). The
StatefulSet couldn't roll forward because the broken pod never reached Ready.
**Fix**: `helm uninstall` + `helm install` to start from a clean slate.

### Error 4 — Access denied on socket, then on TCP

```
$ kubectl exec mariadb-0 -n mariadb -- mysql -uroot -p"$MARIADB_ROOT_PASSWORD"
ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)
sh-5.3$ command terminated with exit code 137
```

Three things to unpack:
1. `$MARIADB_ROOT_PASSWORD` is empty inside the pod. Bitnami uses
   `MARIADB_ROOT_PASSWORD_FILE` (a file mount), not the env var. Use
   `mysql -p"$(cat /opt/bitnami/mariadb/secrets/mariadb-root-password)"`.
2. `root@localhost` is `unix_socket` auth — it ignores passwords and checks
   the caller's UID instead. When the mariadb client sends a password anyway,
   the plugin rejects the auth.
3. Exit 137 = SIGKILL. The liveness probe failed repeatedly (because of point 2),
   and kubelet killed the container.

### Error 5 — Service exists, port 3306 not listening

```
$ mysql -h mariadb.mariadb.svc.cluster.local -uroot -p...
ERROR 2002 (HY000): Can't connect to server on 'mariadb.mariadb.svc.cluster.local' (115)
```

The Kubernetes Service exists and maps to port 3306 correctly, but MariaDB
inside the pod is launched with `--skip-networking`, so nothing listens on TCP.
The service has no backend. To confirm:

```
$ kubectl exec mariadb-0 -n mariadb -- ps aux | grep mariadbd
/opt/bitnami/mariadb/sbin/mariadbd ... --socket=... --skip-networking --skip-slave-start --log-error=/dev/null
                                                                          ^^^^^^^^^^^^^^^^^^^^
```

`--skip-networking` is passed by `/opt/bitnami/scripts/libmariadb.sh`
(`mariadb_start_bg`) and is supposed to be removed in `run.sh` once init
completes. But init never completes because the liveness probe keeps killing
the pod mid-init.

### Error 6 — my.cnf settings get overridden

User added to values.yaml:
```yaml
primary:
  configuration: |
    [mysqld]
    max_allowed_packet = 128M
    skip-networking = 0
    bind-address = 0.0.0.0
```

After `helm upgrade`:
- `cat /opt/bitnami/mariadb/conf/my.cnf` inside the pod shows the new lines. ✓
- `ps aux | grep mariadbd` still shows `--skip-networking` and no `0.0.0.0`. ✗

MariaDB command-line args win over my.cnf. Bitnami's libmariadb.sh passes
`--skip-networking` as an arg, so the `skip-networking = 0` in my.cnf is
silently overridden. The config setting is not "wrong" — it just never has a
chance to take effect.

## What finally worked

Disabling both probes in values.yaml, so init can complete uninterrupted:
```yaml
primary:
  livenessProbe:
    enabled: false
  readinessProbe:
    enabled: false
```

Then `helm uninstall && helm install`. After init completes, `ps aux` shows
`mariadbd` running WITHOUT `--skip-networking`, port 3306 binds, the service
becomes reachable, and TCP-based auth with the password works.

## Final root cause

The whole chain was driven by gotcha #4: the liveness probe's auth mismatch
(using password against `unix_socket` plugin) caused kubelet to kill the
container during init. Every subsequent error (no TCP listener, my.cnf
overridden, persistent CrashLoopBackOff) was a downstream consequence of init
never finishing. Disabling the probe is the workaround; the proper fix is
a custom probe that uses TCP `mysqladmin ping` against the service port
or socket-based auth without a password.
