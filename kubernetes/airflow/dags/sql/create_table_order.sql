CREATE TABLE IF NOT EXISTS "order" (
  id UUID,
  date_order TIMESTAMP,
  date_shipping TIMESTAMP,
  quantity SMALLINT,
  price REAL,
  customer_id UUID REFERENCES customer(id),
  product_id UUID REFERENCES product(id)
);
