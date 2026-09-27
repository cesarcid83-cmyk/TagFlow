import os
import glob
import json
import csv
from datetime import datetime
import pandas as pd

def normalizar_fecha_iso(fecha_raw, hora_raw="00:00:00"):
    if not fecha_raw or str(fecha_raw).strip() == "" or str(fecha_raw).lower() == "nan":
        return ""
    
    f_str = str(fecha_raw).strip().replace('"', '')
    h_str = str(hora_raw).strip().replace('"', '') if hora_raw else "00:00:00"

    if " " in f_str:
        partes = f_str.split(" ")
        f_str = partes[0]
        if len(partes) > 1 and partes[1].strip():
            h_str = partes[1]

    partes_hora = h_str.split(":")
    if len(partes_hora) == 2:
        h_str = f"{partes_hora[0].zfill(2)}:{partes_hora[1].zfill(2)}:00"
    elif len(partes_hora) >= 3:
        h_str = f"{partes_hora[0].zfill(2)}:{partes_hora[1].zfill(2)}:{partes_hora[2].zfill(2)}"

    cadena_unida = f"{f_str} {h_str}"

    formatos_posibles = [
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M"
    ]

    for fmt in formatos_posibles:
        try:
            dt = datetime.strptime(cadena_unida, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

    return cadena_unida

def limpiar_monto(monto_raw):
    if monto_raw is None:
        return 0.0
    s = str(monto_raw).replace("$", "").replace(" ", "").strip()
    if not s or s.lower() == "nan":
        return 0.0
    
    if "," in s and "." not in s:
        s = s.replace(",", ".")
        try:
            return round(float(s), 2)
        except ValueError:
            pass

    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
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

            fechahora_raw = fila.get("FechaHora", "").strip().replace('"', '')
            if not fechahora_raw:
                f_part = fila.get("Fecha", "").strip().replace('"', '')
                h_part = fila.get("Hora", "00:00:00").strip().replace('"', '')
                fecha_norm = normalizar_fecha_iso(f_part, h_part)
            else:
                fecha_norm = normalizar_fecha_iso(fechahora_raw)

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
            fecha_norm = normalizar_fecha_iso(fec, hor)
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
        print(f"[AVISO] Error en RutaPass no facturado ({ruta_archivo}): {e}")
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
            fecha_norm = normalizar_fecha_iso(fec_raw)
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
        print(f"[AVISO] Error en factura RutaPass ({ruta_archivo}): {e}")
    return registros

def procesar_vespucio_norte_nofacturado(ruta_archivo):
    registros = []
    try:
        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec = str(fila.get("Fecha", "")).strip()
            hor = str(fila.get("Hora", "00:00:00")).strip()
            fecha_norm = normalizar_fecha_iso(fec, hor)

            portico_val = str(fila.get("Pórtico", fila.get("Portico", "---"))).strip()
            portico_entrada = f"Pórtico {portico_val}" if portico_val not in ["---", "nan"] else "---"
            tarifa = limpiar_monto(fila.get("Valor", 0))

            registros.append({
                "autopista": "Vespucio Norte",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": portico_entrada,
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "No Facturada",
                "boleta": "---"
            })
    except Exception as e:
        print(f"[AVISO] Error en Vespucio Norte No Facturado ({ruta_archivo}): {e}")
    return registros

def procesar_vespucio_norte_facturado(ruta_archivo, boleta_defecto="10156275"):
    registros = []
    try:
        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec = str(fila.get("Fecha", "")).strip()
            hor = str(fila.get("Hora", "00:00:00")).strip()
            fecha_norm = normalizar_fecha_iso(fec, hor)

            portico_val = str(fila.get("Portico", fila.get("Pórtico", "---"))).strip()
            portico_entrada = f"Pórtico {portico_val}" if portico_val not in ["---", "nan"] else "---"
            tarifa = limpiar_monto(fila.get("Valor", 0))

            registros.append({
                "autopista": "Vespucio Norte",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": portico_entrada,
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "Facturada",
                "boleta": boleta_defecto
            })
    except Exception as e:
        print(f"[AVISO] Error en Vespucio Norte Facturado ({ruta_archivo}): {e}")
    return registros

def procesar_autopase_csv(ruta_archivo, es_facturado=False, boleta_defecto="---"):
    registros = []
    if not os.path.isfile(ruta_archivo):
        return registros

    try:
        delimitador = ";"
        with open(ruta_archivo, "r", encoding="utf-8-sig", errors="ignore") as test_f:
            linea = test_f.readline()
            if linea.count(";") < linea.count(","):
                delimitador = ","

        df = pd.read_csv(ruta_archivo, delimiter=delimitador, dtype=str, encoding="utf-8-sig", on_bad_lines="skip")
        df.columns = [str(c).strip() for c in df.columns]

        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", fila.get("PATENTE", ""))).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec = str(fila.get("Fecha", fila.get("FECHA", ""))).strip()
            hor = str(fila.get("Hora", fila.get("HORA", "00:00:00"))).strip()
            fecha_norm = normalizar_fecha_iso(fec, hor)

            portico = str(fila.get("Pórtico", fila.get("Portico", fila.get("PORTICO", fila.get("PuntoCobro", "---"))))).strip()
            if portico == "nan": portico = "---"

            eje = str(fila.get("Eje", fila.get("Lugar", ""))).strip()
            autopista = "Autopista Central" if ("Ruta 5" in eje or "General Velasquez" in eje or "Velasquez" in eje) else "Autopase"

            monto_col = fila.get("Monto", fila.get("Monto ($)", fila.get("Valor", fila.get("Importe", 0))))
            tarifa = limpiar_monto(monto_col)

            registros.append({
                "autopista": autopista,
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": portico,
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "Facturada" if es_facturado else "No Facturada",
                "boleta": boleta_defecto if es_facturado else "---"
            })
    except Exception as e:
        print(f"[AVISO] Error al procesar Autopase ({os.path.basename(ruta_archivo)}): {e}")

    return registros

def consolidar_cliente(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)

    carpeta_crudos = os.path.join(directorio_raiz, "crudos", id_cliente)
    ruta_destino_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    todos_los_viajes = []

    # 1. Conservar registros de autopistas manuales (AVO/Otros)
    autopistas_gestionadas = ["Costanera Norte", "RutaPass", "Vespucio Norte", "AMB", "Autopase", "Autopista Central"]
    if os.path.exists(ruta_destino_json):
        try:
            with open(ruta_destino_json, "r", encoding="utf-8") as f:
                anteriores = json.load(f)
                for v in anteriores:
                    if v.get("autopista") not in autopistas_gestionadas:
                        todos_los_viajes.append(v)
            print(f"[INFO] Registros base conservados (AVO/Otros): {len(todos_los_viajes)}")
        except Exception as e:
            print(f"[AVISO] Error al leer data.json previo: {e}")

    # 2. Costanera Norte y AMB
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "Costanera_*.csv"))):
        print(f"[PROCESANDO] Costanera: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_csv_costanera(arch))

    # 3. RutaPass No Facturado
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "RutaPass_*.xls*"))):
        print(f"[PROCESANDO] RutaPass No Facturado: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_no_facturado(arch))

    # 4. RutaPass Facturado
    archivos_factura_rp = glob.glob(os.path.join(directorio_raiz, "RutaPass_Factura_*.xlsx")) or \
                          glob.glob(os.path.join(carpeta_crudos, "RutaPass_Factura_*.xlsx"))
    for arch in sorted(archivos_factura_rp):
        print(f"[PROCESANDO] Factura RutaPass: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_facturado(arch))

    # 5. Vespucio Norte Facturado
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "VespucioNorte_Facturado_*.xlsx"))):
        print(f"[PROCESANDO] Vespucio Norte Facturado: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_vespucio_norte_facturado(arch))

    # 6. Vespucio Norte No Facturado
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "VespucioNorte_*.xlsx"))):
        if "Facturado" not in os.path.basename(arch):
            print(f"[PROCESANDO] Vespucio Norte No Facturado: {os.path.basename(arch)}")
            todos_los_viajes.extend(procesar_vespucio_norte_nofacturado(arch))

    # 7. Autopase Facturado
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "Autopase_Facturado_*.csv"))):
        if os.path.isfile(arch):
            nombre = os.path.basename(arch)
            partes = nombre.split("_")
            boleta_num = partes[2] if len(partes) > 2 else "Factura"
            print(f"[PROCESANDO] Autopase Facturado: {nombre} (Boleta: {boleta_num})")
            todos_los_viajes.extend(procesar_autopase_csv(arch, es_facturado=True, boleta_defecto=boleta_num))

    # 8. Autopase No Facturado
    for arch in sorted(glob.glob(os.path.join(carpeta_crudos, "Autopase_*.csv"))):
        if os.path.isfile(arch) and "Facturado" not in os.path.basename(arch):
            print(f"[PROCESANDO] Autopase No Facturado: {os.path.basename(arch)}")
            todos_los_viajes.extend(procesar_autopase_csv(arch, es_facturado=False, boleta_defecto="---"))

    # 9. Deduplicación canónica
    viajes_unicos = {}
    for v in todos_los_viajes:
        clave = f"{v.get('autopista')}_{v.get('patente')}_{v.get('fecha_entrada')}_{v.get('portico_entrada')}_{v.get('tarifa')}"
        viajes_unicos[clave] = v

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    os.makedirs(os.path.dirname(ruta_destino_json), exist_ok=True)
    with open(ruta_destino_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    print(f"\n[ÉXITO] Consolidación completada:")
    print(f"-> Total pasadas únicas en data.json: {len(lista_final)}")
    print(f"-> Guardado en: {ruta_destino_json}")

if __name__ == "__main__":
    consolidar_cliente("automaas")