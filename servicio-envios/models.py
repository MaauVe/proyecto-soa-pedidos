"""
Definición de DDL y sentencias SQL para servicio-envios.
"""

CREATE_SHIPMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    zone TEXT NOT NULL CHECK (zone IN ('LOCAL', 'REGIONAL', 'NACIONAL')),
    recipient_name TEXT NOT NULL,
    shipping_cost REAL NOT NULL CHECK (shipping_cost >= 0),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_shipments_order_id ON shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
"""
