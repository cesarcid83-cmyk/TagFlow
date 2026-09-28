import os
import glob
import time
import shutil
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

directorio_raiz = r"C:\Users\cesar cid\OneDrive\Desktop\TagFlow"
carpeta_cliente = os.path.join(directorio_raiz, "crudos", "automaas")
carpeta_temp = os.path.join(directorio_raiz, "temp_downloads")
ruta_config = os.path.join(directorio_raiz, "config", "clients.json")
ruta_reporte = os.path.join(directorio_raiz, "reporte_descargas_fallidas.txt")

os.makedirs(carpeta_cliente, exist_ok=True)
os.makedirs(carpeta_temp, exist_ok=True)

# Limpiar temporales
for f in glob.glob(os.path.join(carpeta_temp, "*")):
    try:
        if os.path.isfile(f):
            os.remove(f)
    except Exception:
        pass

reporte_errores = []

def cargar_config():
    if os.path.exists(ruta_config):
        try:
            with open(ruta_config, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

todos_los_clientes = cargar_config()
cliente = next((c for c in todos_los_clientes if c.get("id") == "automaas"), {})
creds = cliente.get("credentials", {})
rut_config = creds.get("rut_empresa", "78343019-3")
pass_config = creds.get("password_portal", "Automaas2024*")

opciones = webdriver.ChromeOptions()
opciones.add_argument("--start-maximized")
opciones.add_argument("--disable-blink-features=AutomationControlled")
opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
opciones.add_experimental_option("useAutomationExtension", False)

opciones.add_argument("--safebrowsing-disable-download-protection")
opciones.add_argument("--safebrowsing-disable-extension-blacklist")

prefs = {
    "download.default_directory": carpeta_temp,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": False,
    "safebrowsing.disable_download_protection": True
}
opciones.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=opciones)
wait = WebDriverWait(driver, 20)

def eliminar_modales():
    try:
        driver.execute_script("""
            var cruces = document.querySelectorAll('.close, [aria-label="Close"], button.close, .modal .btn-close, .modal-header button, div[role="dialog"] button');
            cruces.forEach(function(c) { try { c.click(); } catch(e){} });
            var modales = document.querySelectorAll('.modal, .modal-backdrop, [role="dialog"], #modalImagen, .fade.show, .popup');
            modales.forEach(function(m) { m.remove(); });
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';
            document.body.style.paddingRight = '0px';
        """)
        time.sleep(1)
    except Exception:
        pass

def mover_descarga(prefijo_nombre):
    for _ in range(12):
        time.sleep(1.5)
        archivos = [
            f for f in glob.glob(os.path.join(carpeta_temp, "*"))
            if os.path.isfile(f) and not f.endswith(".crdownload") and not f.endswith(".tmp")
        ]
        if archivos:
            mas_reciente = max(archivos, key=os.path.getctime)
            ext = os.path.splitext(mas_reciente)[1]
            timestamp = datetime.now().strftime('%d%m%Y_%H%M%S')
            nuevo_nombre = f"{prefijo_nombre}_{timestamp}{ext}"
            destino = os.path.join(carpeta_cliente, nuevo_nombre)
            if os.path.exists(destino):
                os.remove(destino)
            shutil.move(mas_reciente, destino)
            print(f"       [ÉXITO] Archivo descargado: {nuevo_nombre}")
            return True
    return False

def ejecutar_descarga_boton_excel(prefijo_archivo):
    try:
        time.sleep(1.5)
        clic_ok = driver.execute_script("""
            var btn = document.getElementById('botonExcel');
            if (btn) {
                btn.scrollIntoView({block: 'center'});
                btn.click();
                return true;
            }
            var formExp = document.getElementById('FormularioExportacion');
            if (formExp) {
                formExp.submit();
                return true;
            }
            return false;
        """)
        if clic_ok:
            time.sleep(2)
            if mover_descarga(prefijo_archivo):
                return True
            else:
                reporte_errores.append({
                    "pestana": prefijo_archivo,
                    "motivo": "Bloqueado por análisis antivirus o tiempo de espera agotado."
                })
        else:
            print(f"       [INFO] Sin botón de descarga en esta vista ({prefijo_archivo}).")
    except Exception as e:
        print(f"       [AVISO] No se pudo descargar: {e}")
    return False

try:
    print("\n==========================================")
    print(f"[AUTOPASE] Extracción Nativa de Facturados (RUT: {rut_config})")
    print("==========================================")

    driver.get("https://www.autopase.cl/")
    time.sleep(4)
    eliminar_modales()

    print("[INFO] Abriendo Zona Clientes...")
    btn_clientes = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-clientes-desk")))
    driver.execute_script("arguments[0].click();", btn_clientes)
    time.sleep(2)

    wait.until(EC.element_to_be_clickable((By.ID, "sRUT"))).send_keys(rut_config)
    driver.find_element(By.ID, "sClave").send_keys(pass_config)
    driver.find_element(By.ID, "Enviar").click()
    print("[INFO] Credenciales enviadas.")

    print("\n" + "="*65)
    print("[CONTROL MANUAL]")
    print("Resuelve el CAPTCHA en Chrome si aparece.")
    print("Una vez dentro de la cuenta:")
    print("-> PRESIONA [ENTER] EN ESTA CONSOLA <-")
    print("="*65 + "\n")
    input("Presiona [ENTER] para iniciar la descarga...")

    # Documentos a procesar
    documentos_facturados = [
        {
            "boleta": "0020821947",
            "monto": "$ 2.039.077",
            "hash_url": "RkUgMDAyMDgyMTk0Nw==/Mi4wMzkuMDc3"
        },
        {
            "boleta": "0020625365",
            "monto": "$ 87.535",
            "hash_url": "RkUgMDAyMDYyNTM2NQ==/ODcuNTM1"
        }
    ]

    for i, doc in enumerate(documentos_facturados, 1):
        folio = doc["boleta"]
        monto = doc["monto"]
        h_url = doc["hash_url"]

        print(f"\n=================================================================")
        print(f"[{i}/{len(documentos_facturados)}] PROCESANDO BOLETA: FE {folio} ({monto})")
        print(f"=================================================================")

        # -------------------------------------------------------------
        # PESTAÑA 1: PEAJES AUTOPISTA CENTRAL
        # -------------------------------------------------------------
        print("\n  -> [1/5] Pestaña: Peajes Autopista Central...")
        url_peajes = f"https://www.autopase.cl/cliente/detalleConsumo/peaje_urbana/{h_url}"
        driver.get(url_peajes)
        time.sleep(5)
        eliminar_modales()
        ejecutar_descarga_boton_excel(f"Autopase_Facturado_Central_{folio}")

        # -------------------------------------------------------------
        # PESTAÑA 2: ESTACIONAMIENTO
        # -------------------------------------------------------------
        print("\n  -> [2/5] Pestaña: Estacionamiento...")
        url_est = f"https://www.autopase.cl/cliente/detalleconsumo/estacionamiento/{h_url}"
        driver.get(url_est)
        time.sleep(4)
        eliminar_modales()
        if "no existen registros asociados" not in driver.page_source.lower():
            ejecutar_descarga_boton_excel(f"Autopase_Facturado_Estacionamiento_{folio}")
        else:
            print("       [INFO] Sin registros en Estacionamiento.")

        # -------------------------------------------------------------
        # PESTAÑA 3: AUTOPISTAS INTERURBANAS
        # -------------------------------------------------------------
        print("\n  -> [3/5] Pestaña: Autopistas Interurbanas...")
        url_int = f"https://www.autopase.cl/cliente/detalleconsumo/peaje_interurbana/{h_url}"
        
        # 8300 = Autopista Nueva Aconcagua, 9100 = Ruta Los Libertadores
        interurbanas_map = [
            ("8300", "Autopista_Nueva_Aconcagua"),
            ("9100", "Ruta_Los_Libertadores")
        ]

        for val_ubicacion, tag_conc in interurbanas_map:
            print(f"       • Consultando ubicación: {tag_conc} (value={val_ubicacion})...")
            driver.get(url_int)
            time.sleep(3)
            eliminar_modales()

            # Seleccionar ubicación y enviar formulario POST nativo
            submit_ok = driver.execute_script(f"""
                var form = document.getElementById('form1');
                var select = document.querySelector('select[name="ubicacion"]');
                if (form && select) {{
                    select.value = '{val_ubicacion}';
                    form.submit();
                    return true;
                }}
                return false;
            """)

            if submit_ok:
                time.sleep(5)
                eliminar_modales()
                if "no presenta detalle" not in driver.page_source.lower():
                    ejecutar_descarga_boton_excel(f"Autopase_Facturado_Interurbana_{tag_conc}_{folio}")
                else:
                    print(f"       [INFO] Sin movimientos en {tag_conc}.")
            else:
                print(f"       [AVISO] No se pudo enviar formulario de {tag_conc}.")

        # -------------------------------------------------------------
        # PESTAÑA 4: INFRACCIONES
        # -------------------------------------------------------------
        print("\n  -> [4/5] Pestaña: Infracciones...")
        url_inf = f"https://www.autopase.cl/cliente/detalleconsumo/infracciones/{h_url}"

        # 0002 = Autopista Central, 8400 = Nueva Aconcagua, 9700 = Los Libertadores
        infracciones_map = [
            ("0002", "Autopista_Central"),
            ("8400", "Autopista_Nueva_Aconcagua"),
            ("9700", "Autopista_Los_Libertadores")
        ]

        for val_ubicacion, tag_conc in infracciones_map:
            print(f"       • Consultando infracciones: {tag_conc} (value={val_ubicacion})...")
            driver.get(url_inf)
            time.sleep(3)
            eliminar_modales()

            # Seleccionar ubicación, mantener patente vacía y enviar POST
            submit_ok = driver.execute_script(f"""
                var form = document.getElementById('form1');
                var selectUbic = document.querySelector('select[name="ubicacion"]');
                var selectPat = document.querySelector('select[name="patente"]');
                if (form && selectUbic) {{
                    selectUbic.value = '{val_ubicacion}';
                    if (selectPat) selectPat.value = '';
                    form.submit();
                    return true;
                }}
                return false;
            """)

            if submit_ok:
                time.sleep(5)
                eliminar_modales()
                if "no presenta detalle" not in driver.page_source.lower() and "no existen registros" not in driver.page_source.lower():
                    ejecutar_descarga_boton_excel(f"Autopase_Facturado_Infracciones_{tag_conc}_{folio}")
                else:
                    print(f"       [INFO] Sin infracciones en {tag_conc}.")
            else:
                print(f"       [AVISO] No se pudo enviar formulario de infracciones ({tag_conc}).")

        # -------------------------------------------------------------
        # PESTAÑA 5: OTROS SERVICIOS
        # -------------------------------------------------------------
        print("\n  -> [5/5] Pestaña: Otros Servicios...")
        url_otros = f"https://www.autopase.cl/cliente/detalleconsumo/otros_servicios/{h_url}"
        driver.get(url_otros)
        time.sleep(4)
        eliminar_modales()
        if "no presenta detalle" not in driver.page_source.lower():
            ejecutar_descarga_boton_excel(f"Autopase_Facturado_OtrosServicios_{folio}")
        else:
            print("       [INFO] Sin registros en Otros Servicios.")

        print(f"\n[OK] Boleta FE {folio} finalizada.")

    # Guardar boletas en clients.json al terminar
    tracking = cliente.setdefault("billing_tracking", {}).setdefault("autopase", {})
    tracking["boletas_procesadas"] = [doc["boleta"] for doc in documentos_facturados]
    try:
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump(todos_los_clientes, f, indent=2, ensure_ascii=False)
        print("\n[CONFIG] clients.json actualizado con las boletas procesadas.")
    except Exception as e:
        print(f"[AVISO] Error al guardar config: {e}")

    # Reporte de Auditoría
    print("\n" + "="*70)
    print("         INFORME DE CONTROL: FACTURADOS AUTOPASE")
    print("="*70)
    if not reporte_errores:
        print("[ÉXITO TOTAL] Todas las pestañas con datos descargaron sus archivos CSV.")
    else:
        print(f"[ATENCIÓN] Se registraron {len(reporte_errores)} incidencias:")
        with open(ruta_reporte, "w", encoding="utf-8") as f_rep:
            f_rep.write(f"REPORTE FACTURADOS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for err in reporte_errores:
                linea = f"• [{err['pestana']}] -> {err['motivo']}"
                print(linea)
                f_rep.write(linea + "\n")
        print(f"\n[ARCHIVO GENERADO] Listado guardado en: {ruta_reporte}")
    print("="*70 + "\n")

except Exception as e:
    print(f"\n[ERROR GENERAL]: {e}")
finally:
    driver.quit()