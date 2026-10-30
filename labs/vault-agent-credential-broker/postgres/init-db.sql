-- Seed data for the customers database.
-- All PII here is well-known TEST data (test SSNs, the 4111... test card).

CREATE TABLE customers (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    ssn        TEXT NOT NULL,          -- test values only
    card_last4 TEXT NOT NULL,
    tier       TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    item        TEXT NOT NULL,
    amount_usd  NUMERIC(10, 2) NOT NULL,
    status      TEXT NOT NULL
);

INSERT INTO customers (name, email, ssn, card_last4, tier) VALUES
  ('Ada Lovelace',      'ada@example.com',      '078-05-1120', '1111', 'gold'),
  ('Grace Hopper',      'grace@example.com',    '219-09-9999', '1111', 'gold'),
  ('Alan Turing',       'alan@example.com',     '457-55-5462', '1111', 'standard'),
  ('Katherine Johnson', 'katherine@example.com','078-05-1120', '1111', 'gold'),
  ('Linus Benedict',    'linus@example.com',    '219-09-9999', '1111', 'standard'),
  ('Radia Perlman',     'radia@example.com',    '457-55-5462', '1111', 'standard'),
  ('Barbara Liskov',    'barbara@example.com',  '078-05-1120', '1111', 'gold'),
  ('Dennis Ritchie',    'dennis@example.com',   '219-09-9999', '1111', 'standard');

INSERT INTO orders (id, customer_id, item, amount_usd, status) VALUES
  (1001, 1, 'Mechanical keyboard',      129.99, 'shipped'),
  (1002, 2, 'USB-C dock',               189.00, 'processing'),
  (1003, 3, '27" 4K monitor',           449.50, 'delivered'),
  (1004, 4, 'Noise-cancelling headset', 279.00, 'shipped'),
  (1005, 5, 'Standing desk',            599.99, 'processing'),
  (1006, 6, 'Ergonomic chair',          749.00, 'delivered'),
  (1007, 7, 'Laptop stand',              59.99, 'shipped'),
  (1008, 8, 'Webcam',                    99.00, 'returned'),
  (1009, 1, 'Trackball mouse',           89.50, 'processing'),
  (1010, 3, 'Thunderbolt cable',         39.00, 'delivered');
