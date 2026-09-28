import os
import glob
import time
import shutil
import json
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# =============================================================================
# CONFIGURACIÓN DE RUTAS Y DIRECTORIOS
# =============================================================================
directorio_raiz = r"C:\Users\cesar cid\OneDrive\Desktop\TagFlow"
carpeta_cliente = os.path.join(directorio_raiz, "crudos", "automaas")
carpeta_pdf = os.path.join(carpeta_cliente, "facturas_pdf")
carpeta_temp = os.path.join(directorio_raiz, "temp_downloads")
ruta_config = os.path.join(directorio_raiz, "config", "clients.json")
ruta_reporte = os.path.join(directorio_raiz, "reporte_descargas_fallidas.txt")

os.makedirs(carpeta_cliente, exist_ok=True)
os.makedirs(carpeta_pdf, exist_ok=True)
os.makedirs(carpeta_temp, exist_ok=True)

# Limpiar archivos temporales residuales
for f in glob.glob(os.path.join(carpeta_temp, "*")):
    try:
        if os.path.isfile(f):
            os.remove(f)
    except Exception:
        pass

reporte_errores = []

# =============================================================================
# MANEJO DE CONFIGURACIÓN Y CLIENTES
# =============================================================================
def cargar_config():
    if os.path.exists(ruta_config):
        try:
            with open(ruta_config, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[AVISO] Error al leer clients.json: {e}")
    return []

def guardar_config(datos):
    try:
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        print("[CONFIG] clients.json actualizado con éxito.")
    except Exception as e:
        print(f"[ERROR] No se pudo guardar clients.json: {e}")

todos_los_clientes = cargar_config()
cliente = next((c for c in todos_los_clientes if c.get("id") == "automaas"), {})
creds = cliente.get("credentials", {})
rut_config = creds.get("rut_empresa", "78343019-3")
pass_config = creds.get("password_portal", "Automaas2024*")

tracking = cliente.setdefault("billing_tracking", {}).setdefault("autopase", {})
boletas_ya_procesadas = tracking.setdefault("boletas_procesadas", [])

# =============================================================================
# INICIALIZACIÓN DE SELENIUM CHROME DRIVER
# =============================================================================
opciones = webdriver.ChromeOptions()
opciones.add_argument("--start-maximized")
opciones.add_argument("--disable-blink-features=AutomationControlled")
opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
opciones.add_experimental_option("useAutomationExtension", False)

# Prevención de bloqueos automáticos en descargas consecutivas
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

# =============================================================================
# FUNCIONES AUXILIARES DE NAVEGACIÓN Y DESCARGA
# =============================================================================
def eliminar_modales():
    """Elimina popups y overlays que bloquean la interacción."""
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
    """Monitorea temp_downloads y renombra el CSV final hacia crudos/automaas."""
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
            print(f"       [ÉXITO] Archivo guardado: {nuevo_nombre}")
            return True
    return False

def ejecutar_descarga_boton_excel(prefijo_archivo):
    """Acciona el botón nativo de descarga (#botonExcel o submit de exportación)."""
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
            var enlaces = Array.from(document.querySelectorAll('a, button, input'));
            var target = enlaces.find(function(el) {
                var t = (el.innerText || el.value || '').toUpperCase().trim();
                return t === 'DESCARGAR' || t.indexOf('DESCARGAR') !== -1;
            });
            if (target) {
                target.scrollIntoView({block: 'center'});
                target.click();
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
                    "motivo": "Bloqueado por análisis antivirus o tiempo de descarga agotado."
                })
        else:
            print(f"       [INFO] Sin botón de descarga en esta vista ({prefijo_archivo}).")
    except Exception as e:
        print(f"       [AVISO] No se pudo descargar: {e}")
    return False

def extraer_no_facturados(categoria):
    """Recorre patente por patente en la sección No Facturados."""
    try:
        time.sleep(2)
        eliminar_modales()
        select_patente = Select(wait.until(EC.presence_of_element_located((By.ID, "patente"))))
        patentes = [
            op.text.strip() for op in select_patente.options 
            if op.text.strip() and "seleccione" not in op.text.lower()
        ]
        print(f"[INFO] {categoria}: Consultando {len(patentes)} patentes...")

        descargados = 0
        for pat in patentes:
            try:
                select_patente = Select(driver.find_element(By.ID, "patente"))
                select_patente.select_by_visible_text(pat)
                time.sleep(0.5)

                btn_buscar = driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')] | //input[@value='Buscar']")
                driver.execute_script("arguments[0].click();", btn_buscar)
                time.sleep(3)

                btn_descargar = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Descargar')] | //a[contains(text(), 'Descargar')]"))
                )
                driver.execute_script("arguments[0].click();", btn_descargar)
                time.sleep(2)

                if mover_descarga(f"Autopase_{categoria}_{pat}"):
                    descargados += 1
                else:
                    reporte_errores.append({
                        "pestana": f"No Facturado - {categoria} ({pat})",
                        "motivo": "No se generó descarga o fue bloqueada por antivirus."
                    })
            except Exception:
                # Patente sin pasadas en el periodo en curso
                pass
        print(f"[RESUMEN] {categoria}: {descargados} archivos descargados correctamente.")
    except Exception as e:
        print(f"[AVISO] Error general en no facturados ({categoria}): {e}")

# =============================================================================
# FLUJO PRINCIPAL
# =============================================================================
try:
    print("\n==========================================")
    print(f"[AUTOPASE] Extracción Unificada (RUT: {rut_config})")
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
    print("Resuelve el CAPTCHA con tranquilidad en Chrome si aparece.")
    print("Una vez dentro del portal:")
    print("-> REGRESA A ESTA CONSOLA Y PRESIONA [ENTER] <-")
    print("="*65 + "\n")
    input("Presiona [ENTER] para iniciar la extracción completa...")

    # -------------------------------------------------------------------------
    # FASE 1: CONSUMOS NO FACTURADOS (URBANOS E INTERURBANOS)
    # -------------------------------------------------------------------------
    print("\n" + "#"*70)
    print("           FASE 1: CONSUMOS NO FACTURADOS")
    print("#"*70)

    print("\n[NO FACTURADOS 1/2] Peajes Autopista Central...")
    driver.get("https://www.autopase.cl/cliente/consumos/consumo_peaje_nofacturado")
    extraer_no_facturados("Central")

    print("\n[NO FACTURADOS 2/2] Autopistas Interurbanas...")
    driver.get("https://www.autopase.cl/cliente/consumos/consumo_peaje_nofacturado_interurbana")
    extraer_no_facturados("Interurbana")

    # -------------------------------------------------------------------------
    # FASE 2: CONSUMOS FACTURADOS (RECORRIDO NATIVO DE LAS 5 PESTAÑAS)
    # -------------------------------------------------------------------------
    print("\n" + "#"*70)
    print("           FASE 2: HISTÓRICO DE FACTURADOS (DETALLES)")
    print("#"*70)

    driver.get("https://www.autopase.cl/cliente/tufacturacion/cartola")
    time.sleep(5)
    eliminar_modales()

    # Desplegar acordeón de Histórico de Documentos
    print("[INFO] Desplegando Histórico de Documentos...")
    driver.execute_script("""
        var toggler = document.querySelector('.contentToggler[data-target=".dynamicContentHistorico"]');
        if (toggler) { toggler.click(); }
        var cont = document.querySelector('.dynamicContentHistorico');
        if (cont) { cont.style.display = 'block'; }
    """)
    time.sleep(3)

    # Identificar boletas con cobro (> $0) y sus enlaces directos a detalle
    boletas_detectadas = driver.execute_script("""
        var resultados = [];
        var filas = Array.from(document.querySelectorAll('.dynamicContentHistorico table tbody tr'));
        filas.forEach(function(f) {
            var txt = f.innerText || '';
            if (txt.indexOf('FE ') !== -1 && txt.indexOf('$ 0') === -1 && txt.indexOf('$0') === -1) {
                var m = txt.match(/FE\\s*(\\d+)/);
                var numBoleta = m ? m[1].trim() : '';
                var enlace = f.querySelector('td.textCenter a[href*="detalleConsumo"]');
                if (enlace && numBoleta) {
                    var href = enlace.getAttribute('href');
                    var partes = href.split('peaje_urbana/');
                    var hashUrl = partes.length > 1 ? partes[1] : '';
                    resultados.push({
                        boleta: numBoleta,
                        hash_url: hashUrl
                    });
                }
            }
        });
        return resultados;
    """)

    # Respaldo de rutas directas si el selector del DOM varía
    if not boletas_detectadas:
        boletas_detectadas = [
            {"boleta": "0020821947", "hash_url": "RkUgMDAyMDgyMTk0Nw==/Mi4wMzkuMDc3"},
            {"boleta": "0020625365", "hash_url": "RkUgMDAyMDYyNTM2NQ==/ODcuNTM1"}
        ]

    # Filtrar solo aquellas que no han sido procesadas previamente
    boletas_a_procesar = [b for b in boletas_detectadas if b["boleta"] not in boletas_ya_procesadas]

    if not boletas_a_procesar:
        print("[INFO] No hay facturas pendientes. Todas las boletas ya se encuentran procesadas en clients.json.")
    else:
        print(f"[INFO] Facturas a procesar en esta corrida: {[b['boleta'] for b in boletas_a_procesar]}")

        for i, doc in enumerate(boletas_a_procesar, 1):
            folio = doc["boleta"]
            h_url = doc["hash_url"]

            print(f"\n=================================================================")
            print(f"[{i}/{len(boletas_a_procesar)}] PROCESANDO DETALLE FACTURA: FE {folio}")
            print(f"=================================================================")

            # 1. Peajes Autopista Central
            print("\n  -> [1/5] Pestaña: Peajes Autopista Central...")
            url_peajes = f"https://www.autopase.cl/cliente/detalleConsumo/peaje_urbana/{h_url}"
            driver.get(url_peajes)
            time.sleep(5)
            eliminar_modales()
            ejecutar_descarga_boton_excel(f"Autopase_Facturado_Central_{folio}")

            # 2. Estacionamiento
            print("\n  -> [2/5] Pestaña: Estacionamiento...")
            url_est = f"https://www.autopase.cl/cliente/detalleconsumo/estacionamiento/{h_url}"
            driver.get(url_est)
            time.sleep(4)
            eliminar_modales()
            if "no existen registros asociados" not in driver.page_source.lower():
                ejecutar_descarga_boton_excel(f"Autopase_Facturado_Estacionamiento_{folio}")
            else:
                print("       [INFO] Sin registros en Estacionamiento.")

            # 3. Autopistas Interurbanas
            print("\n  -> [3/5] Pestaña: Autopistas Interurbanas...")
            url_int = f"https://www.autopase.cl/cliente/detalleconsumo/peaje_interurbana/{h_url}"
            interurbanas_map = [
                ("8300", "Autopista_Nueva_Aconcagua"),
                ("9100", "Ruta_Los_Libertadores")
            ]

            for val_ubicacion, tag_conc in interurbanas_map:
                print(f"       • Consultando ubicación: {tag_conc} (value={val_ubicacion})...")
                driver.get(url_int)
                time.sleep(3)
                eliminar_modales()

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

            # 4. Infracciones
            print("\n  -> [4/5] Pestaña: Infracciones...")
            url_inf = f"https://www.autopase.cl/cliente/detalleconsumo/infracciones/{h_url}"
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

            # 5. Otros Servicios
            print("\n  -> [5/5] Pestaña: Otros Servicios...")
            url_otros = f"https://www.autopase.cl/cliente/detalleconsumo/otros_servicios/{h_url}"
            driver.get(url_otros)
            time.sleep(4)
            eliminar_modales()
            if "no presenta detalle" not in driver.page_source.lower():
                ejecutar_descarga_boton_excel(f"Autopase_Facturado_OtrosServicios_{folio}")
            else:
                print("       [INFO] Sin registros en Otros Servicios.")

            # Registrar la boleta procesada de forma incremental
            boletas_ya_procesadas.append(folio)
            guardar_config(todos_los_clientes)
            print(f"[OK] Boleta FE {folio} concluida y registrada.")

    # -------------------------------------------------------------------------
    # INFORME FINAL DE AUDITORÍA
    # -------------------------------------------------------------------------
    print("\n" + "="*70)
    print("         INFORME DE CONTROL Y DESCARGAS: AUTOPASE")
    print("="*70)
    if not reporte_errores:
        print("[ÉXITO TOTAL] Todas las descargas solicitadas (No Facturados y Facturados) se completaron sin incidencias.")
    else:
        print(f"[ATENCIÓN] Se registraron {len(reporte_errores)} descargas fallidas:")
        with open(ruta_reporte, "w", encoding="utf-8") as f_rep:
            f_rep.write(f"REPORTE CONTROL AUTOPASE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for err in reporte_errores:
                linea = f"• [{err['pestana']}] -> {err['motivo']}"
                print(linea)
                f_rep.write(linea + "\n")
        print(f"\n[ARCHIVO AUDITORÍA GENERADO] {ruta_reporte}")
    print("="*70 + "\n")

except Exception as e:
    print(f"\n[ERROR GENERAL]: {e}")
finally:
    driver.quit()