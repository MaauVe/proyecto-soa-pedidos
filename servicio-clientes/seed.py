"""
Datos semilla para el servicio-clientes.
Se cargan automáticamente al arranque si la tabla customers está vacía (RF-1).
"""
import logging

from sqlalchemy.orm import Session

from models import Customer

logger = logging.getLogger("servicio-clientes.seed")

# 5 clientes de prueba: 3 zonas distintas, activos e inactivos mezclados
_SEED_DATA = [
    dict(
        full_name="Ana García López",
        email="ana.garcia@ejemplo.com",
        phone="5551234567",
        delivery_address="Av. Insurgentes Sur 1234, Col. Del Valle, CDMX",
        coverage_zone="Local",
        is_active=True,
    ),
    dict(
        full_name="Carlos Martínez Ruiz",
        email="carlos.martinez@ejemplo.com",
        phone="81 1234 5678",
        delivery_address="Blvd. Ávila Camacho 450, Col. Cumbres, Monterrey, NL",
        coverage_zone="Regional",
        is_active=True,
    ),
    dict(
        full_name="María Fernández Soto",
        email="maria.fernandez@ejemplo.com",
        phone="33 9876 5432",
        delivery_address="Calle 5 de Mayo 789, Col. Centro, Guadalajara, JAL",
        coverage_zone="Nacional",
        is_active=True,
    ),
    dict(
        full_name="Roberto Silva Torres",
        email="roberto.silva@ejemplo.com",
        phone="5557654321",
        delivery_address="Paseo de la Reforma 987, Col. Juárez, CDMX",
        coverage_zone="Regional",
        is_active=True,
    ),
    dict(
        full_name="Laura Vega Mendoza",
        email="laura.vega@ejemplo.com",
        phone="222 345 6789",
        delivery_address="Av. Universidad 321, Col. La Paz, Puebla, PUE",
        coverage_zone="Local",
        is_active=False,  # cliente inactivo — útil para probar casos límite
    ),
]


def seed_customers(session: Session) -> None:
    """
    Inserta clientes de prueba solo si la tabla customers está vacía.
    Si ya existen registros, no hace ningún cambio (idempotente).
    """
    existing = session.query(Customer).count()
    if existing > 0:
        logger.info("Seed omitido: la tabla customers ya contiene %d registros.", existing)
        return

    for data in _SEED_DATA:
        session.add(Customer(**data))

    session.commit()
    logger.info("Seed completado: %d clientes de prueba cargados.", len(_SEED_DATA))
