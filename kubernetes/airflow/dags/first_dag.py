from airflow import DAG
from datetime import datetime
#from airflow.operators.python import PythonOperator
from airflow.providers.standard.operators.python import PythonOperator

with DAG(
    dag_id='first_dag',
    description='My first DAG',
    tags=['datascientest'],
    schedule=None,  # ← remplace schedule_interval=None
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2024, 1, 1),
    }
) as my_dag:

    def print_hello():
        print('Hello from Airflow')

    print_hello_task = PythonOperator(
        task_id='print_hello',
        python_callable=print_hello,
        #queue="kubernetes"
    )

    print_hello_task
  