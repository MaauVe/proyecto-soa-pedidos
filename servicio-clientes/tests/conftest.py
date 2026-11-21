"""
conftest.py — Configuración de pytest para servicio-clientes.
Asegura que el directorio del servicio esté en sys.path para las importaciones.
"""
import sys
from pathlib import Path

# Agrega servicio-clientes/ al path para que pytest resuelva los módulos locales
sys.path.insert(0, str(Path(__file__).parent.parent))
