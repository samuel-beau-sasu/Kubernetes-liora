# Créer un ConfigMap

On utilise nano plutot que vi 

```bash
export KUBE_EDITOR=nano
```

Pour toutes les sessions futures, ajoute la ligne dans ton ~/.bashrc (Ubuntu / bash) :

```bash  
echo 'export KUBE_EDITOR=nano' >> ~/.bashrc
source ~/.bashrc
```

Commençons par créer un fichier configuration MySQL nommé mysqld.cnf pour remplacer le paramètre par défaut et définir max_allowed_packet égal à 128M.

```bash
[mysqld]
max_allowed_packet = 128M
```
Créer un ConfigMap nommé cm-mariadb à partir du fichier précédent :

```bash
 kubectl create configmap cm-mariadb --from-file=mysqld.cnf
```

Créer un ConfigMap nommé cm-mariadb à partir du fichier précédent et le fichier yaml équivalent
```bash
kubectl create configmap cm-mariadb --from-file=mysqld.cnf --dry-run=client -o yaml > cm-mariadb.yaml
```

Créer un ConfigMap nommé cm-mariadb avec un fichier yaml
```bash
apiVersion: v1
kind: ConfigMap
metadata:
    name: cm-mariadb
data:
    mysqld.cnf: |
    [mysqld]
    max_allowed_packet = 128M

kubectl create -f cm-mariadb.yaml
kubectl apply -f cm-mariadb.yaml
```

Suppression
```bash
 kubectl delete configmap cm-mariadb
```

Le contenu du Configmap peut être visualisé de façon exhaustive avec la commande kubectl describe.

```bash
 kubectl describe cm cm-mariadb
```

## Utilisation des secrets et des ConfigMaps

Pour : mariadb-root-password/secret-root-password.yml
```bash
kubectl delete secret mariadb-root-password

kubectl apply -f secret-root-password.yml

kubectl describe secret mariadb-root-password
```

De meme pour : mariadb-user/secret-mariadb-user.yml

## Créer une instance MariaDB

```bash
kubectl create -f statefulset.yml

kubectl exec -it mariadb-0 -- env | grep MARIADB
```
VM: 108.131.12.235

kubectl delete statefulset mariadb
kubectl delete pvc -l app=mariadb
kubectl apply -f statefulset.yml

Vérification
kubectl exec -it mariadb-0 -- env | grep MARIADB

## Notes de relecture du StatefulSet (à finaliser)

Le manifeste statefulset.yml initial contient 3 bugs à corriger :

1. `mountPath: etc/mysql/conf.d` → manque le `/` initial, doit être `/etc/mysql/conf.d`
2. Volume `data` en `emptyDir` sur un StatefulSet = anti-pattern (base effacée à chaque restart du pod). Remplacer par `volumeClaimTemplates` avec storage 1Gi, accessModes ReadWriteOnce
3. StatefulSet reste `Pending` indéfiniment sans Service headless `mariadb` (kind: Service, clusterIP: None, port 3306)

Secrets requis avant l'apply du StatefulSet (sinon `CreateContainerConfigError`) :
- `mariadb-root-password` (clé `password`) → MARIADB_ROOT_PASSWORD
- `mariadb-user` (envFrom) → crée l'utilisateur applicatif au premier boot

Manifeste corrigé esquissé (à finaliser et tester) :

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mariadb
spec:
  serviceName: mariadb
  replicas: 1
  selector:
    matchLabels:
      app: mariadb
  template:
    metadata:
      labels:
        app: mariadb
    spec:
      containers:
        - name: mariadb
          image: docker.io/mariadb:10.4
          ports:
            - containerPort: 3306
          env:
            - name: MARIADB_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mariadb-root-password
                  key: password
          envFrom:
            - secretRef:
                name: mariadb-user
          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
            - name: config
              mountPath: /etc/mysql/conf.d
      volumes:
        - name: config
          configMap:
            name: cm-mariadb
            items:
              - key: mysqld.cnf
                path: mysqld.cnf
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: mariadb
spec:
  clusterIP: None
  selector:
    app: mariadb
  ports:
    - port: 3306
      targetPort: 3306
```

## Pièges kubectl à retenir

- `kubectl exec POD COMMANDE` → KO depuis kubectl 1.18. Toujours `kubectl exec POD -- COMMANDE`
- `kubectl create` vs `apply` : `create` one-shot (erreur si existe), `apply` idempotent (created / configured / unchanged)
- `--dry-run=client -o yaml` : génère le YAML sans créer l'objet (à rediriger dans un fichier avec `>`)
- `cm-mariadb` (cluster) ≠ `cm-mariadb.yaml` (disque) : l'objet dans le cluster est la réalité, le YAML n'est qu'une intention
- `|-` en YAML : literal block, sauts de ligne préservés, pas de newline final — indispensable pour les fichiers de config multi-lignes comme `mysqld.cnf`
- `KUBE_EDITOR=nano` pour éviter vi sur `kubectl edit`
```
