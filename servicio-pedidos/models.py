"""
Definición del esquema DDL en SQLite para servicio-pedidos.
Tablas: orders (pedidos) y order_items (líneas de pedido).
"""

CREATE_ORDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    coverage_zone TEXT NOT NULL,
    shipping_cost REAL NOT NULL CHECK (shipping_cost >= 0),
    total_amount REAL NOT NULL CHECK (total_amount >= 0),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED')),
    shipment_id INTEGER,
    compensation_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_ORDER_ITEMS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    subtotal REAL NOT NULL CHECK (subtotal >= 0)
);
"""

CREATE_SCHEMA_SQL = f"{CREATE_ORDERS_TABLE_SQL}\n{CREATE_ORDER_ITEMS_TABLE_SQL}"
