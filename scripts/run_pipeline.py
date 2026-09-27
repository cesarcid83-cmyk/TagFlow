import os
import sys
import json
import subprocess
from datetime import datetime

def cargar_configuracion(ruta_raiz):
    ruta_json = os.path.join(ruta_raiz, "config", "clients.json")
    if not os.path.exists(ruta_json):
        print(f"[ERROR] No se encontro el archivo de configuracion: {ruta_json}")
        return []
    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            clientes = json.load(f)
            return [c for c in clientes if c.get("active", True)]
    except Exception as e:
        print(f"[ERROR] Error al leer {ruta_json}: {e}")
        return []

def ejecutar_script_python(ruta_script):
    """Ejecuta un script usando el mismo interprete de Python activo"""
    if not os.path.exists(ruta_script):
        print(f"[OMITIDO] Script no encontrado: {os.path.basename(ruta_script)}")
        return False

    nombre = os.path.basename(ruta_script)
    print(f"\n=======================================================")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] EJECUTANDO: {nombre}")
    print(f"=======================================================")
    
    try:
        resultado = subprocess.run([sys.executable, ruta_script], check=False)
        if resultado.returncode == 0:
            print(f"[EXITO] {nombre} finalizo correctamente.")
            return True
        else:
            print(f"[AVISO] {nombre} finalizo con codigo de salida: {resultado.returncode}")
            return False
    except Exception as e:
        print(f"[FALLO] Error al ejecutar {nombre}: {e}")
        return False

def ejecutar_pipeline_completo():
    inicio_tiempo = datetime.now()
    directorio_scripts = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_scripts)
    directorio_extractors = os.path.join(directorio_raiz, "extractors")

    print("=======================================================")
    print(f"INICIANDO PIPELINE TAGFLOW - {inicio_tiempo.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=======================================================")

    clientes = cargar_configuracion(directorio_raiz)
    if not clientes:
        print("[ERROR] No hay clientes activos para procesar.")
        return

    # Mapeo de identificadores de servicio a sus scripts en extractors/
    extractores_disponibles = {
        "avo": os.path.join(directorio_extractors, "avo.py"),
        "costanera": os.path.join(directorio_extractors, "costanera.py"),
        "rutapass": os.path.join(directorio_extractors, "rutapass.py"),
        "autopase": os.path.join(directorio_extractors, "autopase.py"),
        "vespucio_sur": os.path.join(directorio_extractors, "vespucio_sur.py"),
        "vespucio_norte": os.path.join(directorio_extractors, "vespucio_norte.py")
    }

    # 1. Recorrer clientes y ejecutar sus extractores activos
    for cliente in clientes:
        c_id = cliente.get("id")
        c_name = cliente.get("name", c_id)
        servicios = cliente.get("services", [])
        print(f"\n>>> Procesando cliente: {c_name} (ID: {c_id})")
        print(f">>> Servicios suscritos: {', '.join(servicios)}")

        for servicio in servicios:
            if servicio in extractores_disponibles:
                ruta_extractor = extractores_disponibles[servicio]
                ejecutar_script_python(ruta_extractor)
            else:
                print(f"[INFO] Servicio '{servicio}' sin extractor asignado actualmente.")

    # 2. Procesamiento de facturas adicionales (si existe el procesador de RutaPass)
    script_factura_rp = os.path.join(directorio_scripts, "procesar_factura_rutapass.py")
    if os.path.exists(script_factura_rp):
        ejecutar_script_python(script_factura_rp)

    # 3. Consolidación de datos con merge.py
    script_merge = os.path.join(directorio_scripts, "merge.py")
    print(f"\n=======================================================")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CONSOLIDANDO REGISTROS GLOBALES")
    print(f"=======================================================")
    ejecutar_script_python(script_merge)

    duracion = datetime.now() - inicio_tiempo
    print("\n=======================================================")
    print(f"[FINALIZADO] Pipeline completo ejecutado en {duracion.total_seconds():.1f} segundos.")
    print("=======================================================\n")

if __name__ == "__main__":
    ejecutar_pipeline_completo()