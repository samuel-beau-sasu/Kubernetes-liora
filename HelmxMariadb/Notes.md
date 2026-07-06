1- création du namespace mariadb
kubectl create namespace mariadb

2- Nous allons principalement travailler dans le namespace mariadb
sudo kubectl config set-context --current --namespace=mariadb

kubectl config get-contexts

3- Ajouter le dépôt Helm Bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

3.1- 
helm show values bitnami/mariadb > values.yaml

4- Garder (ou appliquer) tes Secrets actuels

kubectl delete secret-mariadb-user.yaml
kubectl delete secret-root-password.yaml

kubectl apply -f secret-mariadb-user.yaml
kubectl apply -f secret-root-password.yaml

5- Lancer l'installation avec Helm
helm upgrade --install mariadb bitnami/mariadb -f mariadb-values.yaml

5.1- Supprimer l'installation de mariadb
helm uninstall mariadb -n mariadb

vérification 
kubectl get all -n mariadb

kubectl exec -it mariadb-0 -- /bin/sh

mysql -uroot -p"$(cat /opt/bitnami/mariadb/secrets/mariadb-root-password)" -e "SHOW VARIABLES LIKE 'max_allowed_packet';"

mysql -h mariadb.mariadb.svc.cluster.local -uroot -p"$(cat /opt/bitnami/mariadb/secrets/mariadb-root-password)" -e "SHOW VARIABLES LIKE 'max_allowed_packet';"

Token QWEN:
sk-ws-H.YMRMYY.SIUy.MEUCIG0GatEE71s8f6wWKXlHsCkSScvoSweoIbQrXL0zVQvDAiEAi3u0zU1mCM-SY6MiiGzKu2EMXdvuHq2N6pjT2uCCHGw




DatascientstMariadb@@.
Datascientest2023@!!




# solution Claude

Voici la procédure pour repartir de zéro avec Helm uniquement :
    
    1. Nettoyage complet (pour être sûr)
    bash
    helm uninstall mariadb -n mariadb
    kubectl delete pvc -l app.kubernetes.io/instance=mariadb -n mariadb
    kubectl delete secret mariadb-root-password -n mariadb --ignore-not-found
    kubectl delete secret mariadb-user -n mariadb --ignore-not-found
    
    
    2. Installation Helm "Standard"
    Je vais utiliser uniquement le chart Bitnami, sans fichier de valeurs externe, pour garantir une installation propre.
    bash
    helm install mariadb bitnami/mariadb -n mariadb
    
    
    3. Récupération du mot de passe généré par Helm
    Comme Helm a créé un mot de passe aléatoire, on va le récupérer pour pouvoir se connecter :
    bash
    export MARIADB_ROOT_PASSWORD=$(kubectl get secret --namespace mariadb mariadb-root-password -o jsonpath="{.data.mariadb-root-password}" | base64 -d)

    echo "Mot de passe : $MARIADB_ROOT_PASSWORD" mariadb-root-password

    kubectl get secret mariadb-root-password -o jsonpath='{.data.mariadb-root-password}' | base64 --decode

    kubectl get secret --namespace mariadb mariadb-root-password -o jsonpath='{.data.mariadb-root-password}' | base64 -d

    4. Commande complète depuis le client

    kubectl run mariadb-client --rm --tty -i --restart='Never' \
      --image registry-1.docker.io/bitnami/mariadb:latest \
      --namespace mariadb \
      --env="MARIADB_ROOT_PASSWORD=$(kubectl get secret --namespace mariadb mariadb-root-password -o jsonpath='{.data.mariadb-root-password}' | base64 -d)" \
      --command -- bash
    
    5. Test de connexion

    mariadb -h mariadb.mariadb.svc.cluster.local -u root -p"$MARIADB_ROOT_PASSWORD" --skip-ssl -e "SELECT 1;"



    mariadb -h mariadb -u root -p"$MARIADB_ROOT_PASSWORD" --skip-ssl -e "SELECT 1;"


    kubectl run mariadb-client --rm -it --restart=Never \
--image=bitnami/mariadb:12.3.2 -n mariadb -- bash


# Solution gemma

La Solution Finale et Garantie
    
    Pour que vos secrets personnels soient enfin pris en compte, nous devons impérativement supprimer les données persistantes pour forcer MariaDB à s'initialiser une nouvelle fois avec vos propres valeurs.
    
    Exécutez ces commandes exactement dans cet ordre :
    
    1. Nettoyage radical (Installation + Données)
    bash
    helm uninstall mariadb -n mariadb
    kubectl delete pvc -l app.kubernetes.io/instance=mariadb -n mariadb
    
    (L'étape du delete pvc est la plus importante ici : elle efface le mot de passe aléatoire stocké sur le disque).
    
    2. Installation avec vos secrets
    bash
    helm install mariadb bitnami/mariadb -f /home/ubuntu/HelmxMariadb/mariadb-fixed-values.yaml -n mariadb
    
    
    3. Attente et Vérification
    Attendez 30 secondes, puis vérifiez que le pod est Ready :
    bash
    kubectl get pods -n mariadb
    
    
    4. Le Test Final
    Lancer le client et utiliser votre mot de passe Datascientest2023@!! :
    bash
    kubectl run mariadb-client --rm --tty -i --restart='Never' \
      --image registry-1.docker.io/bitnami/mariadb:latest \
      --namespace mariadb \
      --command -- bash
    
    Une fois dedans :
    bash
    mariadb -h mariadb.mariadb.svc.cluster.local -u root -p'Datascientest2023@!!' --skip-ssl -e "SELECT 1;"
    
    
    Pourquoi ça va marcher cette fois ?
    Parce qu'en supprimant le PVC, la ligne Using persisted data disparaîtra des logs et sera remplacée par Initializing MariaDB database. À ce moment précis, MariaDB lira vos secrets YAML pour créer la base, et votre mot de passe sera enfin le bon.