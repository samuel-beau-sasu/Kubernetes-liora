import json
import pandas as pd
import numpy as np

def extract_orders(data_directory):
    orders = []
    with open(f'{data_directory}/to_ingest/bronze/orders.json') as json_file:
        for line in json_file:
            orders.append(json.loads(line))
    return orders

def build_df_customer_product(orders):
    customers = []
    products = []
    for order in orders:
        customers.append(order['customer'])
        products.append(order['product'])
    df_customer = pd.DataFrame(customers)
    df_product = pd.DataFrame(products)
    df_customer = df_customer.drop_duplicates(subset=['id'])
    df_product = df_product.drop_duplicates(subset=['id'])
    return df_customer, df_product

def transform_df_customer(df_customer):
    df_delivery_address = pd.json_normalize(df_customer['delivery_address'])
    df_customer = df_customer.reset_index().drop(columns=['index'])
    df_customer = pd.concat([df_customer[['id', 'lastname', 'firstname', 'sex']], df_delivery_address], axis=1)
    df_customer['street_number'] = df_customer['street_number'].astype(int)
    return df_customer

def transform_orders(orders):
    for order in orders:
        order['customer_id'] = order['customer']['id']
        order['product_id'] = order['product']['id']
        product_price = order['product']['price']
        order['price'] = round(product_price * order['quantity'], 2)
        order.pop('customer', None)
        order.pop('product', None)
    return orders

def transform_df_product(df_product):
    df_product['weight'] = round(df_product['weight'].astype(float), 2)
    df_product['price'] = round(df_product['price'].astype(float), 2)
    return df_product

def load_data(orders, df_customer, df_product, data_directory):
    df_customer.to_csv(f'{data_directory}/to_ingest/silver/customers.csv', index=False)
    df_product.to_csv(f'{data_directory}/to_ingest/silver/products.csv', index=False)
    with open(f'{data_directory}/to_ingest/silver/orders.json', 'w') as output_file:
        for order in orders:
            json.dump(order, output_file)
            output_file.write('\n')
    print(f'orders, customers and products loaded in {data_directory}/to_ingest/silver directory')

if __name__ == '__main__':
    data_directory = 'data'
    orders = extract_orders(data_directory)
    df_customer, df_product = build_df_customer_product(orders)
    df_customer = transform_df_customer(df_customer.copy())
    df_product = transform_df_product(df_product.copy())
    orders =  transform_orders(orders.copy())
    load_data(orders, df_customer, df_product, data_directory)
