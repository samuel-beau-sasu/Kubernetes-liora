# ollama launch hermes --model gemma4:31b-cloud

   🏗️ Architecture : Pipeline Airflow $\rightarrow$ MariaDB
    
    text
                                      [ UTILISATEUR / ADMIN ]
                                                │
                                                ▼
                                      ┌────────────────────┐
                                      │   Interface Web    │
                                      │      Airflow       │
                                      └──────────┬─────────┘
                                                 │
                                                 │ (1) Orchestration
                                                 ▼
        ┌───────────────────────────────────────────────────────────────────────────────────────────┐
        │                           CLUSTER KUBERNETES                                              │
        │                                                                                           │
        │  ┌──────────────────────┐            ┌─────────────────────────────────────┐              │
        │  │    PODS AIRFLOW      │            │       POD MARIADB (StatefulSet)     │              │
        │  │ (Scheduler / Worker) │            │            (mysql-0)                │              │
        │  └──────────┬───────────┘            └──────────────────┬──────────────────┘              │
        │             │                                           │                                 │
        │             │ (2) Requêtes SQL                          │ (3) Persistance                 │
        │             └────────────────────────────────────────────►                                │
        │                                                          │                                │
        │                                                          ▼                                │
        │                                                  ┌────────────────────────────────┐       │
        │                                                  │    VOLUME PERSISTANT (PV)      │       │
        │                                                  │     (/var/lib/mysql)           │       │
        │                                                  └─────────────────────────────── ┘       │
        │                                                                                           │
        │  ┌───────────────────── ─┐            ┌─────────────────────────────────────┐             │
        │  │  VOLUMES AIRFLOW (PV) │            │      LOGIQUE ETL (App Pods)         │             │
        │  │   - /dags             │◄───────────┤   - Python Load (JSON ➔ DB)         │             │
        │  │   - /logs             │            │   - Python Transform (DB ➔ DB)      │             │
        │  └───────────────────────┘            └──────────────────┬──────────────────┘             │
        │                                                          │                                │
        │                                                          ▼                                │
        │                                                  ┌────────────────────────────────┐       │
        │                                                  │      DONNÉES SOURCES (S3/Local)│       │
        │                                                  │      (JSON Orders)             │       │
        │                                                  └────────────────────────────────┘       │
        └──────────────────────────────────────────────────────────────────────────────────────── ──┘
    
1- création du namespace airflow
kubectl create namespace airflow

2- Nous allons principalement travailler dans le namespace airflow
sudo kubectl config set-context --current --namespace=airflow

2.1- Affichez le détail de nos contexts.
kubectl config get-contexts

Étape 1 : Déploiement des Secrets
    Avant de lancer la base de données, elle doit avoir ses mots de passe. Sans cela, le pod MariaDB entrera en erreur immédiate (CrashLoopBackOff).

kubectl apply -f /home/ubuntu/kubernetes/MariaxAirflow/infrastructure/secret-root-password.yml
kubectl apply -f /home/ubuntu/kubernetes/MariaxAirflow/infrastructure/secret-mariadb-user.yml

Dans : /home/ubuntu/kubernetes/MariaxAirflow/infrastructure
kubectl apply -f secret-root-password.yml
kubectl apply -f secret-mariadb-user.yml

Lister les secrets
kubectl get secrets

Supprimer les secrets
kubectl delete secret mariadb-user
kubectl delete secret mariadb-root-password

Étape 2 : Le Service Headless


kubectl apply -f /home/ubuntu/kubernetes/MariaxAirflow/infrastructure/mariadb-service.yml -n airflow

Dans : /home/ubuntu/kubernetes/MariaxAirflow/infrastructure
kubectl apply -f mariadb-service.yml -n airflow

Étape 3 : Le déploiement du StatefulSet MariaDB 

kubectl apply -f /home/ubuntu/kubernetes/MariaxAirflow/infrastructure/statefulset.yml -n airflow

Dans : /home/ubuntu/kubernetes/MariaxAirflow/infrastructure
kubectl apply -f statefulset.yml -n airflow

# Notes PV PVC 

1. Le concept : Provisionnement Statique vs Dynamique
    
    Le Provisionnement Statique (Ce que nous faisons ici)
    C'est comme si tu achetais un disque dur physique, que tu le branchais et que tu disais à Kubernetes : "Voici un disque de 5Go, il est là, utilise-le".
    *   Le PV (PersistentVolume) : C'est la ressource physique (le disque). C'est l'administrateur qui le crée.
    *   Le PVC (PersistentVolumeClaim) : C'est la "requête" de l'utilisateur. Il dit : "J'ai besoin d'un disque de 5Go avec tel accès".
    *   Le Binding : Kubernetes cherche un PV qui correspond exactement à la requête du PVC et les "marie".
    
    Le Provisionnement Dynamique (L'option StorageClass)
    C'est comme si tu commandais un disque sur Amazon. Tu ne sais pas où il est physiquement, tu demandes juste la capacité, et Amazon (le Cloud Provider) crée le disque pour toi instantanément.
    *   Le StorageClass (SC) : C'est le "catalogue" de disques disponibles (ex: "SSD Rapide", "HDD Lent", "AWS EBS").
    *   Le PVC : Tu crées ton PVC en spécifiant simplement la storageClassName.
    *   L'Automate : Kubernetes voit la demande $\rightarrow$ il appelle l'API du Cloud (AWS, Azure, GCP) $\rightarrow$ le Cloud crée le disque $\rightarrow$ Kubernetes crée automatiquement le PV correspondant $\rightarrow$ Binding.
    
    
    
    2. Pourquoi ne l'utilise-t-on pas ici ?
    
    Il y a trois raisons principales dans ton contexte actuel :
    
    A. L'environnement de Labo (Kind/Minikube/VM)
    Le provisionnement dynamique nécessite un "Driver" (CSI) qui communique avec un fournisseur de stockage. Dans un cluster local ou une VM simple, il n'y a pas de "Cloud Provider" pour créer des disques à la volée. Si on utilise une StorageClass sans avoir de driver installé, le PVC restera en Pending éternellement car personne ne répondra à la commande "Crée-moi un disque".
    
    B. Le contrôle total du chemin (hostPath)
    Pour ton projet, on veut souvent que les données soient stockées dans un dossier précis de ton serveur (ex: /home/ubuntu/mariadb_data) pour pouvoir les sauvegarder ou les inspecter facilement. Le provisionnement dynamique cache le chemin physique ; le provisionnement statique nous permet de dire : "Utilise exactement ce dossier sur le disque".
    
    C. La spécificité du StatefulSet
    Le StatefulSet crée des PVC automatiquement via volumeClaimTemplates. S'il n'y a pas de StorageClass capable de créer des volumes dynamiquement, la seule façon pour que le pod mariadb-0 démarre est qu'un PV existe déjà et "attende" d'être réclamé.
    
    En résumé :
    
    | Caractéristique    | PV Manuel (Statique)                        | StorageClass (Dynamique)             |
    |--------------------|---------------------------------------------|--------------------------------------|
    | Création du disque | Manuelle par l'humain                       | Automatique par le Cloud/Driver      |
    | Contrôle           | Total (on choisit le dossier/disque)        | Abstrait (on choisit la performance) |
    | Usage idéal        | Labos, serveurs on-premise, fichiers locaux | Production Cloud (EKS, GKE, AKS)     |
    | Complexité         | Plus de fichiers YAML à gérer               | Très simple (un seul PVC suffit)     |
    
    C'est pour cela que dans ton cas, nous allons créer un PV manuel. Nous allons définir précisément où les données de MariaDB doivent atterrir sur ton disque dur pour être sûrs que le Pod puisse enfin démarrer.

#---------------------

Étape 1 : Créer la ConfigMap manquante dans le bon namespace
kubectl create configmap cm-mariadb --from-file=mysqld.cnf -n airflow

Étape 2 : Vérifier
kubectl get configmap -n airflow

sudo mkdir -p /mnt/mariadb_data
sudo chmod 777 /mnt/mariadb_data

kubectl delete pv mariadb-pv
kubectl apply -f mariadb-pv.yml -n airflow

kubectl apply -f mariadb-pvc.yml -n airflow

test
git push origin master --force

# Déploiement

Voici la procédure complète et les commandes exactes pour lancer le projet. J'ai structuré cela par étapes logiques pour garantir que chaque couche soit opérationnelle avant de passer à la suivante.

📋 Guide de déploiement : Projet MariaxAirflow

Étape 1 : Déploiement de l'infrastructure de stockage et sécurité
On commence par les secrets et les volumes, car sans eux, la base de données ne peut pas démarrer.

bash
Aller dans le dossier infrastructure
cd ~/kubernetes/MariaxAirflow/infrastructure

Appliquer les secrets (mots de passe)
kubectl apply -f secret-root-password.yml
kubectl apply -f secret-mariadb-user.yml

Appliquer les volumes MariaDB (PV et PVC)
kubectl apply -f mariadb-pv.yml
kubectl apply -f mariadb-pvc.yml

Appliquer les volumes Airflow (DAGs et Logs)
kubectl apply -f airflow-local-dags-folder-pv.yaml
kubectl apply -f airflow-local-dags-folder-pvc.yaml
kubectl apply -f airflow-local-logs-folder-pv.yaml
kubectl apply -f airflow-local-logs-folder-pvc.yaml


Option 1 : La méthode propre (Supprimer les Pods d'abord)
Il faut supprimer tout ce qui pourrait utiliser ces volumes.
Supprimer TOUS les PVC du namespace actuel
kubectl delete pvc --all

Supprimer TOUS les PV (Attention : action radicale)
kubectl delete pv --all

Supprimer tous les pods dans tous les namespaces (ou ciblez vos namespaces spécifiques)
kubectl delete pods --all-namespaces


Option 2 : La méthode "Force Brute" (Supprimer les Finalizers)
Si vous voulez forcer la suppression immédiate sans chercher quel Pod bloque, vous devez supprimer le "verrou" (finalizer) de chaque ressource. C'est la méthode la plus rapide quand on est en phase de test.

Pour les PVC :
bash
kubectl get pvc -A -o name | xargs -I {} kubectl patch {} -p '{"metadata":{"finalizers":null}}' --type=merge


Pour les PV :
bash
kubectl get pv -o name | xargs -I {} kubectl patch {} -p '{"metadata":{"finalizers":null}}' --type=merge


Étape 2 : Déploiement de la base de données MariaDB
On lance le serveur de base de données.

bash
Appliquer la configuration et le service réseau
kubectl create configmap cm-mariadb --from-file=mysqld.cnf
kubectl apply -f mariadb-service.yml

Lancer le StatefulSet MariaDB
kubectl apply -f statefulset.yml

VERIFICATION : Attendre que le pod soit "Running"
kubectl get pods -w

Note : Si le pod MariaDB redémarre en boucle, vérifiez les logs avec kubectl logs <nom-du-pod>.

Étape 3 : Déploiement d'Airflow
Une fois que la base est stable, on déploie l'orchestrateur.

bash
Utiliser Helm pour déployer Airflow avec vos valeurs personnalisées
Assurez-vous d'être dans le dossier airflow
cd ~/kubernetes/MariaxAirflow/airflow

helm install airflow apache-airflow/airflow -f my_values.yaml -n airflow --create-namespace


Étape 4 : Vérification finale et Accès
Une fois tout déployé, vérifiez que tout communique.

bash
Vérifier l'état de tous les services
kubectl get all -n airflow

Pour accéder à l'interface web d'Airflow (si pas de LoadBalancer)
kubectl port-forward svc/airflow-webserver 8082:8080 -n airflow

L'interface sera alors accessible sur http://localhost:8080.
34.247.167.93:8080

Le Port-Forward (La plus rapide pour le test)
Vous créez un tunnel direct entre votre machine et le pod.
    
Lancez cette commande dans un terminal séparé :

kubectl port-forward svc/airflow-api-server 8080:8080 -n airflow


💡 Rappel important pour le build des images (App)
Si vous devez builder les images pour les pods de chargement/transformation, n'oubliez pas de vous placer dans les dossiers spécifiques :

Pour le chargement (Load) :
bash
cd ~/kubernetes/MariaxAirflow/app/order/docker/prod/python_load
docker build -t my-python-load:latest .


Pour la transformation (Transform) :
bash
cd ~/kubernetes/MariaxAirflow/app/order/docker/prod/python_transform
docker build -t my-python-transform:latest .

# Création de l'utilisateur admin
kubectl exec deployment/airflow-api-server -n airflow -- airflow users create \
  --username admin \
  --password admin \
  --firstname admin \
  --lastname user \
  --role Admin \
  --email admin@example.com