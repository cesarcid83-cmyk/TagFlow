import os
import glob
import json
import hashlib
import pandas as pd

def limpiar_tarifa(valor):
    """
    Convierte cualquier formato de tarifa (int, float, string con coma o punto)
    a float redondeado a 2 decimales.
    Ejemplos: 158.25 -> 158.25 | '$1.250,50' -> 1250.5 | 1269 -> 1269.0
    """
    if pd.isnull(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)
    
    val_str = str(valor).replace("$", "").replace(" ", "").strip()
    if not val_str or val_str == "---":
        return 0.0
    
    if "," in val_str and "." in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
        
    try:
        return round(float(val_str), 2)
    except ValueError:
        return 0.0

def generar_hash_transito(fila):
    """Genera una clave única a partir de los datos invariables del viaje."""
    patente = str(fila.get("patente", "")).strip().upper()
    fecha = str(fila.get("fecha_entrada", "")).strip()
    portico = str(fila.get("portico_entrada", "")).strip().upper()
    autopista = str(fila.get("autopista", "")).strip().upper()
    
    cadena_id = f"{autopista}_{patente}_{fecha}_{portico}"
    return hashlib.md5(cadena_id.encode("utf-8")).hexdigest()

def procesar_archivo_avo(ruta_excel):
    """Lee y estandariza los registros de un archivo Excel de AVO."""
    df = pd.read_excel(ruta_excel)
    
    registros = []
    for _, fila in df.iterrows():
        reg = {
            "autopista": "AVO",
            "patente": str(fila.get("Patente", "")).strip(),
            "fecha_entrada": str(fila.get("Fecha Entrada", "")).strip(),
            "portico_entrada": str(fila.get("Portico Entrada", "")).strip(),
            "fecha_salida": str(fila.get("Fecha Salida", "")).strip(),
            "portico_salida": str(fila.get("Portico Salida", "")).strip(),
            "categoria": str(fila.get("Categoria", "")).strip(),
            "tarifa": limpiar_tarifa(fila.get("Tarifa", 0)),
            "tipo_tarifa": str(fila.get("Tipo Tarifa", "")).strip(),
            "estado": str(fila.get("Estado", "")).strip(),
            "boleta": str(fila.get("Boleta", "")).strip() if pd.notnull(fila.get("Boleta")) else ""
        }
        reg["id_transito"] = generar_hash_transito(reg)
        registros.append(reg)
        
    return registros

def consolidar_cliente(client_id, base_dir=None):
    """
    Consolida todos los crudos de data/<client_id>/raw/, deduplica por ID único
    y actualiza data/<client_id>/consolidated.json y docs/<client_id>/data.json
    """
    if base_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    raw_dir = os.path.join(base_dir, "data", client_id, "raw")
    consolidated_file = os.path.join(base_dir, "data", client_id, "consolidated.json")
    docs_client_dir = os.path.join(base_dir, "docs", client_id)
    docs_data_file = os.path.join(docs_client_dir, "data.json")

    os.makedirs(docs_client_dir, exist_ok=True)

    # 1. Cargar datos consolidados existentes (si existen)
    existentes = {}
    if os.path.exists(consolidated_file):
        try:
            with open(consolidated_file, "r", encoding="utf-8") as f:
                datos_antiguos = json.load(f)
                for item in datos_antiguos:
                    if "id_transito" in item:
                        existentes[item["id_transito"]] = item
        except Exception as e:
            print(f"[AVISO] Error leyendo archivo consolidado previo: {e}")

    conteo_inicial = len(existentes)

    # 2. Leer archivos crudos de AVO (*.xlsx)
    archivos_avo = glob.glob(os.path.join(raw_dir, "avo_*.xlsx")) + glob.glob(os.path.join(raw_dir, "AVO_*.xlsx"))
    
    for ruta in archivos_avo:
        try:
            viajes = procesar_archivo_avo(ruta)
            for v in viajes:
                # Regla de idempotencia: actualiza o inserta por clave única
                existentes[v["id_transito"]] = v
        except Exception as err:
            print(f"[ERROR] No se pudo procesar {ruta}: {err}")

    # 3. Guardar consolidado acumulativo
    datos_actualizados = list(existentes.values())
    
    # Orden descendente por fecha
    datos_actualizados.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    with open(consolidated_file, "w", encoding="utf-8") as f:
        json.dump(datos_actualizados, f, ensure_ascii=False, indent=2)

    with open(docs_data_file, "w", encoding="utf-8") as f:
        json.dump(datos_actualizados, f, ensure_ascii=False, indent=2)

    print(f"\n==========================================")
    print(f"[CONSOLIDACIÓN] Cliente: {client_id}")
    print(f"Total registros previos: {conteo_inicial}")
    print(f"Total registros consolidados: {len(datos_actualizados)}")
    print(f"Nuevos añadidos: {len(datos_actualizados) - conteo_inicial}")
    print(f"Archivos guardados en:")
    print(f"  - {consolidated_file}")
    print(f"  - {docs_data_file}")
    print(f"==========================================")

def ejecutar_merge_global():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "config", "clients.json")

    if not os.path.exists(config_path):
        print(f"[ERROR] No se encontró config/clients.json")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        clientes = json.load(f)

    for cliente in clientes:
        if cliente.get("active", True):
            consolidar_cliente(cliente["id"], base_dir)

if __name__ == "__main__":
    ejecutar_merge_global()