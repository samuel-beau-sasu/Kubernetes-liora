from airflow import DAG
from datetime import datetime, timezone
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
import os
import requests

def get_auth_token():
    response = requests.post(
        "http://airflow-api-server:8080/auth/token",
        json={"username": "admin", "password": "admin"}
    )
    if response.status_code in (200, 201):
        return response.json()["access_token"]
    else:
        raise RuntimeError(f"Failed to get token: {response.text}")

def create_conn(**kwargs):
    api_url = "http://airflow-api-server:8080/api/v2/connections"
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{api_url}/{kwargs['conn_id']}",
        headers=headers
    )
    print(f"GET connection status: {response.status_code}")

    if response.status_code == 404:
        payload = {
            "connection_id": kwargs['conn_id'],
            "conn_type": kwargs['conn_type'],
            "host": kwargs['host'],
            "login": kwargs['login'],
            "password": kwargs['password'],
            "schema": kwargs['schema'],
            "port": kwargs['port']
        }
        response = requests.post(api_url, json=payload, headers=headers)
        print(f"POST connection status: {response.status_code}")
        if response.status_code == 201:
            print("Connection Created successfully")
        else:
            raise RuntimeError(f"Failed to create connection: {response.text}")
    elif response.status_code == 200:
        print("Connection already exists")
    else:
        raise RuntimeError(f"Unexpected error: {response.text}")

with DAG(
    dag_id='init_order_v8',
    tags=['order', 'datascientest'],
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2024, 1, 1, tzinfo=timezone.utc),
    },
    schedule=None,
    catchup=False
) as dag:

    create_postgres_conn = PythonOperator(
        task_id='create_postgres_conn',
        python_callable=create_conn,
        op_kwargs={
            'conn_id': 'postgres',
            'conn_type': 'postgres',
            'host': os.getenv("AIRFLOW_POSTGRESQL_SERVICE_HOST"),
            'login': 'postgres',
            'password': 'postgres',
            'schema': 'postgres',
            'port': 5432
        }
    )

    create_table_customer = SQLExecuteQueryOperator(
        task_id='create_table_customer',
        conn_id='postgres',
        sql='sql/create_table_customer.sql'
    )

    create_table_product = SQLExecuteQueryOperator(
        task_id='create_table_product',
        conn_id='postgres',
        sql='sql/create_table_product.sql'
    )

    create_table_order = SQLExecuteQueryOperator(
        task_id='create_table_order',
        conn_id='postgres',
        sql='sql/create_table_order.sql'
    )

    create_postgres_conn >> [create_table_customer, create_table_product]
    [create_table_customer, create_table_product] >> create_table_order
    