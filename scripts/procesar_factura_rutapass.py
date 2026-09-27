import os
import glob
import pandas as pd

def generar_excel_factura_rutapass():
    # Directorio raíz TagFlow (un nivel arriba de scripts/)
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    carpeta_crudos = os.path.join(directorio_raiz, "crudos", "automaas")
    
    # Busca el archivo descargado
    patron = os.path.join(carpeta_crudos, "*1790498830*.xls*")
    archivos = glob.glob(patron) or glob.glob(os.path.join(carpeta_crudos, "Transitos__*.xls*"))
    
    if not archivos:
        # Busca en Descargas por si no se movió a crudos
        descargas_user = os.path.join(os.path.expanduser("~"), "Downloads")
        archivos = glob.glob(os.path.join(descargas_user, "*1790498830*.xls*"))

    if not archivos:
        print("[ERROR] No se encontro el archivo Transitos__1790498830.xls")
        return

    ruta_archivo = archivos[0]
    print(f"[PROCESANDO] Leyendo: {ruta_archivo}")

    try:
        df = pd.read_excel(ruta_archivo)
    except Exception:
        df = pd.read_html(ruta_archivo)[0]

    df.columns = [str(c).strip() for c in df.columns]

    registros = []
    for _, fila in df.iterrows():
        patente = str(fila.get("Patente", "")).strip()
        if not patente or patente.lower() == "nan":
            continue

        fecha_str = str(fila.get("Fecha", "")).strip()
        hora_str = str(fila.get("Hora", "00:00:00")).strip()
        if len(hora_str.split(":")) == 2:
            hora_str += ":00"
        
        fecha_completa = f"{fecha_str} {hora_str}"

        monto_raw = str(fila.get("Monto", "0")).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
        try:
            tarifa = float(monto_raw)
        except ValueError:
            tarifa = 0.0

        registros.append({
            "Autopista": "RutaPass",
            "Patente": patente,
            "Fecha Entrada": fecha_completa,
            "Portico Entrada": str(fila.get("Punto_Cobro", "---")).strip(),
            "Portico Salida": "---",
            "Tarifa": tarifa,
            "Estado": "Facturada",
            "Boleta": "3457040"
        })

    df_resultado = pd.DataFrame(registros)

    # Guarda el reporte Excel en la carpeta raíz TagFlow
    ruta_salida = os.path.join(directorio_raiz, "RutaPass_Factura_3457040.xlsx")
    df_resultado.to_excel(ruta_salida, index=False)

    print(f"\n[EXITO] Archivo Excel generado: {ruta_salida}")
    print(f"Total transitos facturados: {len(df_resultado)}")
    total_monto = int(df_resultado['Tarifa'].sum())
    print(f"Monto total sumado: ${total_monto:,}".replace(",", "."))

if __name__ == "__main__":
    generar_excel_factura_rutapass()