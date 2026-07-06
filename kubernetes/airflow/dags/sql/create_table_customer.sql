CREATE TABLE IF NOT EXISTS customer (
  id UUID PRIMARY KEY,
  lastname VARCHAR,
  firstname VARCHAR,
  sex VARCHAR,
  street_number SMALLINT,
  street_name VARCHAR,
  city VARCHAR,
  postcode VARCHAR,
  region VARCHAR,
  modification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
