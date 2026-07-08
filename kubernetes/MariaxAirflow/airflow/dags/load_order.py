from airflow import DAG
from datetime import datetime, timezone
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret
from kubernetes.client import models as k8s

secret_database = Secret(
  deploy_type="env",
  deploy_target="DATABASE",
  secret="sql-conn"
)

secret_user = Secret(
  deploy_type="env",
  deploy_target="USER",
  secret="sql-conn"
)

secret_password = Secret(
  deploy_type="env",
  deploy_target="PASSWORD",
  secret="sql-conn"
)

volume = k8s.V1Volume(
  name="order-data-folder",
  persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(
    claim_name="order-data-folder"
  )
)

volume_mount = k8s.V1VolumeMount(
  name="order-data-folder",
  mount_path="/app/data/to_ingest"
)

with DAG(
  dag_id='load_order',
  tags=['order', 'datascientest'],
  default_args={
    'owner': 'airflow',
    #'start_date': days_ago(0, minute=1),
    'start_date': datetime(2024, 1, 1, tzinfo=timezone.utc),
    },
  #schedule_interval='0 17 * * *',
  schedule='0 17 * * *',
  catchup=False
) as dag:

    python_transform = KubernetesPodOperator(
        task_id="python_transform",
        image="chokosk8/order-python-transform",
        cmds=["python3", "main.py"],
        volumes=[volume],
        volume_mounts=[volume_mount]
    )

    python_load = KubernetesPodOperator(
        task_id="python_load",
        image="chokosk8/order-python-load",
        cmds=["python3", "main.py"],
        secrets=[secret_database, secret_user, secret_password],
        volumes=[volume],
        volume_mounts=[volume_mount]
    )

    python_transform >> python_load