from airflow import DAG
#from airflow.utils.dates import days_ago
from datetime import datetime, timezone
#from airflow.operators.python_operator import PythonOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow import settings
from airflow.models.connection import Connection
#from airflow.operators.postgres_operator import PostgresOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
import os

conn_keys = ['conn_id', 'conn_type', 'host', 'login', 'password', 'schema']

def get_postgres_conn_conf():
    postgres_conn_conf = {}
    postgres_conn_conf['host'] = os.getenv("AIRFLOW_POSTGRESQL_SERVICE_HOST")
    postgres_conn_conf['port'] = os.getenv("AIRFLOW_POSTGRESQL_SERVICE_PORT")
    if (postgres_conn_conf['host'] == None):
        raise TypeError("The AIRFLOW_POSTGRESQL_SERVICE_HOST isn't defined")
    elif (postgres_conn_conf['port'] == None):
        raise TypeError("The AIRFLOW_POSTGRESQL_SERVICE_PORT isn't defined")
    postgres_conn_conf['conn_id'] = 'postgres'
    postgres_conn_conf['conn_type'] = 'postgres'
    postgres_conn_conf['login'] = 'postgres'
    postgres_conn_conf['password'] = 'postgres'
    postgres_conn_conf['schema'] = 'postgres'
    return postgres_conn_conf

def create_conn(**kwargs):
    session = settings.Session()
    print("Session created")
    connections = session.query(Connection)
    print("Connections listed")
    if not kwargs['conn_id'] in [connection.conn_id for connection in connections]:
        conn_params = { key: kwargs[key] for key in conn_keys }
        conn = Connection(**conn_params)
        session.add(conn)
        session.commit()
        print("Connection Created")
    else:
        print("Connection already exists")
    session.close()

postgres_conn_conf = get_postgres_conn_conf()

with DAG(
    dag_id='init_order',
    tags=['order', 'datascientest'],
    default_args={
        'owner': 'airflow',
        #'start_date': days_ago(0, minute=1),
        'start_date': datetime(2024, 1, 1, tzinfo=timezone.utc),
    },
    catchup=False
) as dag:

    create_postgres_conn = PythonOperator(
        task_id='create_postgres_conn',
        python_callable=create_conn,
        op_kwargs=postgres_conn_conf
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
