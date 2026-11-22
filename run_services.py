import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

SERVICES = [
    ("servicio-clientes",   ROOT / "servicio-clientes",   [PYTHON, "-m", "uvicorn", "main:app", "--port", "8001"]),
    ("servicio-inventario", ROOT / "servicio-inventario", [PYTHON, "-m", "uvicorn", "main:app", "--port", "8002"]),
    ("servicio-envios",     ROOT / "servicio-envios",     [PYTHON, "-m", "uvicorn", "main:app", "--port", "8003"]),
    ("servicio-pedidos",    ROOT / "servicio-pedidos",    [PYTHON, "-m", "uvicorn", "main:app", "--port", "8004"]),
    ("cliente-web",         ROOT / "cliente-web",         [PYTHON, "-m", "http.server", "5500"]),
]

processes = []

try:
    print("Iniciando servicios de LogiFlow SOA...\n")
    for name, cwd, cmd in SERVICES:
        proc = subprocess.Popen(cmd, cwd=str(cwd))
        processes.append((name, proc))
        time.sleep(0.4)

    print("\nTodos los servicios estan corriendo:")
    print("  - Cliente Web:         http://localhost:5500")
    print("  - Servicio Clientes:   http://localhost:8001/docs")
    print("  - Servicio Inventario: http://localhost:8002/docs")
    print("  - Servicio Envios:     http://localhost:8003/docs")
    print("  - Servicio Pedidos:    http://localhost:8004/docs")
    print("\nPresiona Ctrl+C para detener todos los servicios.\n")

    for _, proc in processes:
        proc.wait()

except KeyboardInterrupt:
    print("\nDeteniendo todos los servicios...")
    for name, proc in processes:
        proc.terminate()
    for _, proc in processes:
        proc.wait()
    print("Servicios detenidos correctamente.")