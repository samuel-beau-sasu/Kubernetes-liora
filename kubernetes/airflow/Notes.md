1- création du namespace airflow
kubectl create namespace airflow

2- Nous allons principalement travailler dans le namespace test-airflow
sudo kubectl config set-context --current --namespace=airflow

2.1- Affichez le détail de nos contexts.
kubectl config get-contexts

3-  Chargez les valeurs par défauts utilisées pour ces templates dans un fichier nommé `values.yaml`.
helm show values apache-airflow/airflow > values.yaml

4- création de : my_values.yaml

dags:
  persistence:
    enabled: true
    existingClaim: airflow-local-dags-folder

logs:
  persistence:
    enabled: true
    existingClaim: airflow-local-logs-folder

uid: 1000
gid: 1000

dagProcessor:
  env:
  - name: AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL
    value: "10"

executor: CeleryExecutor

# Ajout des dépendances Python pour l'ensemble du cluster Airflow
pipPackages:
  - "apache-airflow-providers-postgres"


6- créer un PersistentVolume et un PersistentVolumeClaim

La seule règle d'or à retenir pour vos prochains déploiements : Toujours créer les bases de stockage (PV, PVC, Secrets) AVANT de lancer le helm install.

mkdir dags
mkdir logs

kubectl apply -f airflow-local-dags-folder-pv.yaml
kubectl apply -f airflow-local-dags-folder-pvc.yaml
kubectl apply -f airflow-local-logs-folder-pv.yaml
kubectl apply -f airflow-local-logs-folder-pvc.yaml

Vérification
kubectl get pv | grep test-airflow
kubectl get pvc -n test-airflow

7- creer les secrets
/home/ubuntu/kubernetes/airflow/order
kubectl apply -f sql-conn-secret.yaml

8- Installation
helm upgrade --install airflow apache-airflow/airflow \
  --namespace=airflow \
  --create-namespace \
  -f my_values.yaml

9.1- vérifiez la santé des pods.
kubectl get pods

9.2- Listez les services du namespace courant, soit airflow.
kubectl get svc

9- Créez le port-forward.

52.212.96.149:8080

#Pour le namespace test-airflow → port 8080
kubectl port-forward svc/airflow-api-server --address 0.0.0.0 8080:8080 --namespace=airflow

10- Création du DAG : init_order

wget https://dst-de.s3.eu-west-3.amazonaws.com/kubernetes_fr/airflow/init_order.tar
tar xvf init_order.tar
rm init_order.tar

c'est le DAG : init_order_v8.py

11- Création du DAG : load_order

11.1- Ajoutons les données !

mkdir -p order/data/to_ingest/bronze
mkdir order/data/to_ingest/silver
wget https://dst-de.s3.eu-west-3.amazonaws.com/airflow/order_example/orders.tar -P order/data
tar xvf order/data/orders.tar -C order/data
rm order/data/orders.tar

12- nous devons créer un PV et un PVC afin de rendre accessible les données à n'importe quel nœud.

kubectl create -f order-data-folder-pv.yaml
kubectl apply -f order-data-folder-pv.yaml

kubectl create -f order-data-folder-pvc.yaml

13- DAG load_order


###------------------------------------------------------------------------------------

Étape 1 : Supprimer les Namespaces

kubectl delete namespace airflow
kubectl delete namespace test-airflow

Étape 2 : Nettoyer les Persistent Volumes (PV)

kubectl get pv

kubectl delete pv order-data-folder
kubectl delete pv airflow-local-dags-folder
kubectl delete pv airflow-local-logs-folder
kubectl delete pv pvc-74ecd2c0-63e0-4c8c-8fda-c94dd4e7cad3 
kubectl delete pv pvc-e42d604a-3358-4b10-95d2-17b2739e571d

kubectl delete ns airflow airflow

kubectl delete deploy,sts,ds,job,cronjob,pod -n airflow --all

kubectl delete pvc -n airflow --all