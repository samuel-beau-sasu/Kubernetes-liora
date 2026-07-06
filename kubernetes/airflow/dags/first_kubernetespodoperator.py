from airflow import DAG
from datetime import datetime
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

with DAG(
    dag_id='first_kubernetespodoperator',
    description='My first DAG with KubernetesPodOperator',
    tags=['datascientest'],
    #schedule_interval=None,
    schedule=None,
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2024, 1, 1),
    }
) as my_dag:

    hello_world = KubernetesPodOperator(
        task_id="hello_world",
        image="hello-world"
    )

    hello_world