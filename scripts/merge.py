import os
import glob
import json
import csv
from datetime import datetime
import pandas as pd

def parsear_fecha_estandar(fecha_str, hora_str="00:00:00"):
    """Normaliza cualquier fecha (DD/MM/YYYY o DD-MM-YYYY) a YYYY-MM-DD HH:MM:SS"""
    if not fecha_str or str(fecha_str).strip() == "" or str(fecha_str).lower() == "nan":
        return ""
    
    texto = f"{str(fecha_str).strip()} {str(hora_str).strip()}".strip()
    texto = texto.replace("  ", " ")
    
    formatos = [
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d"
    ]
    for fmt in formatos:
        try:
            dt = datetime.strptime(texto, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return texto

def limpiar_monto(monto_raw):
    if monto_raw is None:
        return 0.0
    s = str(monto_raw).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def procesar_csv_costanera(ruta_archivo):
    registros = []
    with open(ruta_archivo, mode="r", encoding="utf-8-sig", errors="ignore") as f:
        lector = csv.DictReader(f, delimiter=";")
        for fila in lector:
            patente = fila.get("Patente", "").strip().replace('"', '')
            if not patente:
                continue

            fecha_norm = parsear_fecha_estandar(fila.get("FechaHora", "").strip().replace('"', ''))
            portico = fila.get("PuntoCobro", "").strip().replace('"', '')
            tarifa = limpiar_monto(fila.get("Importe", "0"))
            nombre_corto = fila.get("NombreCorto", "CN").strip().replace('"', '')
            autopista = "Costanera Norte" if nombre_corto == "CN" else nombre_corto

            registros.append({
                "autopista": autopista,
                "patente": patente,
                "fecha_entrada": fecha_norm,
                "portico_entrada": portico if portico else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "No Facturada",
                "boleta": "---"
            })
    return registros

def procesar_rutapass_no_facturado(ruta_archivo):
    registros = []
    try:
        try:
            df = pd.read_excel(ruta_archivo)
        except Exception:
            df = pd.read_html(ruta_archivo)[0]

        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec = str(fila.get("Fecha", "")).strip()
            hor = str(fila.get("Hora", "00:00:00")).strip()
            fecha_norm = parsear_fecha_estandar(fec, hor)
            pto = str(fila.get("Punto_Cobro", "---")).strip()
            tarifa = limpiar_monto(fila.get("Monto", 0))

            registros.append({
                "autopista": "RutaPass",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": pto if pto != "nan" else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "No Facturada",
                "boleta": "---"
            })
    except Exception as e:
        print(f"[AVISO] Error al leer RutaPass no facturado ({ruta_archivo}): {e}")
    return registros

def procesar_rutapass_facturado(ruta_archivo):
    registros = []
    try:
        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec_raw = str(fila.get("Fecha Entrada", "")).strip()
            fecha_norm = parsear_fecha_estandar(fec_raw)
            pto = str(fila.get("Pórtico Entrada", fila.get("Portico Entrada", "---"))).strip()
            tarifa = limpiar_monto(fila.get("Tarifa", 0))
            boleta = str(fila.get("Boleta", "3457040")).strip()

            registros.append({
                "autopista": "RutaPass",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": pto if pto != "nan" else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "Facturada",
                "boleta": boleta if boleta else "3457040"
            })
    except Exception as e:
        print(f"[AVISO] Error al leer factura RutaPass ({ruta_archivo}): {e}")
    return registros

def consolidar_cliente(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)

    carpeta_crudos = os.path.join(directorio_raiz, "crudos", id_cliente)
    ruta_destino_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    todos_los_viajes = []

    # Cargar AVO u otros tránsitos previos existentes
    if os.path.exists(ruta_destino_json):
        try:
            with open(ruta_destino_json, "r", encoding="utf-8") as f:
                anteriores = json.load(f)
                # Conservar registros que no sean ni Costanera ni RutaPass para reincorporar frescos
                for v in anteriores:
                    if v.get("autopista") not in ["Costanera Norte", "RutaPass"]:
                        todos_los_viajes.append(v)
                print(f"[INFO] Datos de otras autopistas conservados: {len(todos_los_viajes)} registros.")
        except Exception as e:
            print(f"[AVISO] Error al leer data.json previo: {e}")

    # 1. Costanera Norte (No facturados)
    for arch in glob.glob(os.path.join(carpeta_crudos, "Costanera_*.csv")):
        print(f"[PROCESANDO] Costanera: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_csv_costanera(arch))

    # 2. RutaPass (No facturados)
    for arch in glob.glob(os.path.join(carpeta_crudos, "RutaPass_*.xls*")):
        print(f"[PROCESANDO] RutaPass No Facturado: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_no_facturado(arch))

    # 3. RutaPass (Facturados)
    archivos_facturas = glob.glob(os.path.join(directorio_raiz, "RutaPass_Factura_*.xlsx")) or glob.glob(os.path.join(carpeta_crudos, "RutaPass_Factura_*.xlsx"))
    for arch in archivos_facturas:
        print(f"[PROCESANDO] RutaPass Factura: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_facturado(arch))

    # Deduplicación con clave única
    viajes_unicos = {}
    for v in todos_los_viajes:
        clave = f"{v.get('autopista')}_{v.get('patente')}_{v.get('fecha_entrada')}_{v.get('portico_entrada')}_{v.get('tarifa')}"
        viajes_unicos[clave] = v

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    os.makedirs(os.path.dirname(ruta_destino_json), exist_ok=True)
    with open(ruta_destino_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    print(f"\n[ÉXITO] Consolidación finalizada:")
    print(f"-> Total general consolidado: {len(lista_final)} pasadas")
    print(f"-> Guardado en: {ruta_destino_json}")

if __name__ == "__main__":
    consolidar_cliente("automaas")