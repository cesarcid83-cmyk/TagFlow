import os
import glob
import re
import pandas as pd
import numpy as np

directorio_raiz = r"C:\Users\cesar cid\OneDrive\Desktop\TagFlow"
carpeta_crudos = os.path.join(directorio_raiz, "crudos", "automaas")
carpeta_salida = os.path.join(directorio_raiz, "data", "processed")
os.makedirs(carpeta_salida, exist_ok=True)
archivo_consolidado = os.path.join(carpeta_salida, "automaas_consolidado.csv")

def limpiar_monto(valor):
    if pd.isna(valor):
        return 0.0
    val_str = str(valor).replace("$", "").replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return float(val_str)
    except Exception:
        return 0.0

def procesar_archivos():
    archivos = glob.glob(os.path.join(carpeta_crudos, "*.csv"))
    if not archivos:
        print(f"[AVISO] No se encontraron archivos CSV en {carpeta_crudos}")
        return

    registros = []

    for ruta in archivos:
        nombre_base = os.path.basename(ruta)
        
        # Mapeo de estado y concesionaria a partir del nombre del archivo
        es_facturado = "Facturado" in nombre_base
        estado_facturacion = "Facturado" if es_facturado else "No Facturado"
        
        # Extracción de boleta si existe
        match_boleta = re.search(r"(\d{10})", nombre_base)
        num_boleta = match_boleta.group(1) if match_boleta else ""

        # Identificación de la concesionaria
        if "Nueva_Aconcagua" in nombre_base:
            concesionaria = "Autopista Nueva Aconcagua"
        elif "Los_Libertadores" in nombre_base:
            concesionaria = "Ruta Los Libertadores"
        elif "Central" in nombre_base:
            concesionaria = "Autopista Central"
        elif "Estacionamiento" in nombre_base:
            concesionaria = "Estacionamientos"
        elif "Interurbana" in nombre_base:
            concesionaria = "Autopista Interurbana"
        else:
            concesionaria = "Otras Concesiones"

        tipo_servicio = "Infracción" if "Infracciones" in nombre_base else "Tránsito Tag"

        try:
            # Lectura flexible probando codificaciones y delimitadores
            try:
                df = pd.read_csv(ruta, sep=None, engine='python', encoding='utf-8')
            except Exception:
                df = pd.read_csv(ruta, sep=None, engine='python', encoding='latin-1')

            if df.empty:
                continue

            # Normalización de encabezados en minúsculas y sin tildes/espacios
            df.columns = [
                str(c).strip().lower()
                .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                .replace(" ", "_").replace("(", "").replace(")", "").replace("$", "")
                for c in df.columns
            ]

            # Detección de columna de patente
            col_patente = next((c for c in df.columns if "patente" in c), None)
            # Detección de columna de fecha
            col_fecha = next((c for c in df.columns if "fecha" in c and "hora" not in c), None)
            # Detección de columna de hora
            col_hora = next((c for c in df.columns if "hora" in c and "ingreso" not in c and "salida" not in c), None)
            # Detección de pórtico / lugar
            col_portico = next((c for c in df.columns if "portico" in c or "plaza" in c), None)
            col_lugar = next((c for c in df.columns if "lugar" in c or "eje" in c), None)
            # Detección de monto
            col_monto = next((c for c in df.columns if "monto" in c or "valor" in c), None)

            for _, fila in df.iterrows():
                patente_val = str(fila[col_patente]).strip() if col_patente and not pd.isna(fila[col_patente]) else ""
                
                # Omitir filas de resumen, encabezados repetidos o líneas vacías
                if not patente_val or "total" in patente_val.lower() or "patente" in patente_val.lower():
                    continue

                monto_val = limpiar_monto(fila[col_monto]) if col_monto else 0.0

                registros.append({
                    "concesionaria": concesionaria,
                    "estado_facturacion": estado_facturacion,
                    "num_boleta": num_boleta,
                    "tipo_servicio": tipo_servicio,
                    "patente": patente_val,
                    "fecha": str(fila[col_fecha]).strip() if col_fecha and not pd.isna(fila[col_fecha]) else "",
                    "hora": str(fila[col_hora]).strip() if col_hora and not pd.isna(fila[col_hora]) else "",
                    "portico": str(fila[col_portico]).strip() if col_portico and not pd.isna(fila[col_portico]) else "",
                    "lugar": str(fila[col_lugar]).strip() if col_lugar and not pd.isna(fila[col_lugar]) else "",
                    "monto": monto_val,
                    "archivo_origen": nombre_base
                })

        except Exception as e:
            print(f"[ERROR] No se pudo procesar el archivo {nombre_base}: {e}")

    if registros:
        df_final = pd.DataFrame(registros)
        # Eliminar posibles duplicados idénticos de pasadas
        df_final.drop_duplicates(subset=["concesionaria", "patente", "fecha", "hora", "monto", "estado_facturacion"], inplace=True)
        df_final.to_csv(archivo_consolidado, index=False, encoding="utf-8-sig")
        print("\n=======================================================")
        print(f"[CONSOLIDACIÓN COMPLETADA] Se procesaron {len(df_final)} registros.")
        print(f"[DESTINO] {archivo_consolidado}")
        print("=======================================================")
    else:
        print("[AVISO] No se extrajeron filas válidas de los archivos.")

if __name__ == "__main__":
    procesar_archivos()