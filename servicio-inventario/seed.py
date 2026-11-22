"""
Datos semilla para el servicio-inventario.
Se cargan automáticamente al arranque si la tabla products está vacía (RF-1).
"""
import logging
import sqlite3
from datetime import UTC, datetime
from typing import Dict, List

logger = logging.getLogger("servicio-inventario.seed")

# 5 productos de prueba: variados precios, pesos y niveles de stock, incluyendo 1 inactivo con stock 0
SEED_PRODUCTS: List[Dict] = [
    {
        "sku": "LAPTOP-001",
        "name": "Laptop Ultradelgada 14\"",
        "description": "Laptop ligera y potente con procesador de última generación.",
        "unit_price": 12500.00,
        "weight_kg": 1.5,
        "stock": 20,
        "is_active": 1,
    },
    {
        "sku": "MOUSE-002",
        "name": "Mouse Inalámbrico Ergonómico",
        "description": "Mouse óptico inalámbrico 2.4GHz con diseño ergonómico.",
        "unit_price": 350.00,
        "weight_kg": 0.15,
        "stock": 150,
        "is_active": 1,
    },
    {
        "sku": "TECLADO-003",
        "name": "Teclado Mecánico RGB",
        "description": "Teclado mecánico con switches táctiles y retroiluminación RGB.",
        "unit_price": 980.00,
        "weight_kg": 0.9,
        "stock": 75,
        "is_active": 1,
    },
    {
        "sku": "MONITOR-004",
        "name": "Monitor 27\" 4K UHD",
        "description": "Monitor profesional IPS 4K con tasa de refresco 60Hz.",
        "unit_price": 8900.00,
        "weight_kg": 5.2,
        "stock": 10,
        "is_active": 1,
    },
    {
        "sku": "AURICULARES-005",
        "name": "Auriculares Bluetooth ANC",
        "description": "Auriculares inalámbricos con cancelación activa de ruido.",
        "unit_price": 1450.00,
        "weight_kg": 0.3,
        "stock": 0,
        "is_active": 0,
    },
]


def seed_products(conn: sqlite3.Connection) -> int:
    """
    Inserta los productos semilla si la tabla products está completamente vacía.
    Es idempotente: si ya existen registros, no realiza ninguna acción.
    Retorna el número de productos insertados.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM products;")
    row = cursor.fetchone()
    count = row["total"] if isinstance(row, sqlite3.Row) else row[0]

    if count > 0:
        logger.info("La tabla 'products' ya contiene %d registros. Omitiendo seed.", count)
        return 0

    now_iso = datetime.now(UTC).isoformat()
    inserted = 0

    with conn:
        for item in SEED_PRODUCTS:
            conn.execute(
                """
                INSERT INTO products (sku, name, description, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item["sku"].upper(),
                    item["name"],
                    item["description"],
                    item["unit_price"],
                    item["weight_kg"],
                    item["stock"],
                    item["is_active"],
                    now_iso,
                    now_iso,
                ),
            )
            inserted += 1

    logger.info("Seed completado exitosamente: %d productos insertados.", inserted)
    return inserted
