from airflow import DAG
from datetime import datetime, timezone
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

with DAG(
    dag_id='init_order_v6',
    tags=['order', 'datascientest'],
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2024, 1, 1, tzinfo=timezone.utc),
    },
    schedule=None,
    catchup=False
) as dag:

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

    [create_table_customer, create_table_product] >> create_table_order