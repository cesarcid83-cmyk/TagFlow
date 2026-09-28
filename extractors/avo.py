import os
import time
import glob
import shutil
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

def extraer_avo(client_id, rut, password, base_dir=None):
    """
    Ejecuta la extracción de viajes de AVO para un cliente específico
    y guarda los archivos Excel en crudos/<client_id>/
    """
    if base_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    target_raw_dir = os.path.join(base_dir, "crudos", client_id)
    temp_download_dir = os.path.join(base_dir, "temp_downloads", f"avo_{client_id}")

    os.makedirs(target_raw_dir, exist_ok=True)
    os.makedirs(temp_download_dir, exist_ok=True)

    print(f"\n==========================================")
    print(f"[AVO] Iniciando extracción para: {client_id} (RUT: {rut})")
    print(f"==========================================")

    # AVO requiere RUT sin puntos ni guion
    rut_limpio = rut.replace(".", "").replace("-", "").strip()

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    prefs = {
        "download.default_directory": temp_download_dir,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    archivos_descargados = []

    try:
        print("[INFO] Abriendo portal AVO...")
        driver.get("https://www.avo.cl/")
        
        btn_ov = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.login-toggler")))
        driver.execute_script("arguments[0].click();", btn_ov)
        time.sleep(2)
        
        driver.find_element(By.ID, "email").send_keys(rut_limpio)
        driver.find_element(By.ID, "password").send_keys(password)
        
        btn_submit = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), 'INGRESAR')]"))
        )
        driver.execute_script("arguments[0].click();", btn_submit)
        time.sleep(4)
        
        print("[INFO] Navegando a detalle de viajes...")
        driver.get("https://www.avo.cl/cliente/detalle_viajes")
        time.sleep(3)
        
        # Rango de fechas: desde 01-08-2026 hasta hoy
        fecha_inicio = "01-08-2026"
        fecha_actual = datetime.now().strftime("%d-%m-%Y")
        rango_fechas = f"{fecha_inicio} - {fecha_actual}"
        
        driver.execute_script(f"""
            var input = document.querySelector('input[name="daterange"]');
            if (input) {{
                input.value = '{rango_fechas}';
                $(input).trigger('change');
            }}
        """)
        time.sleep(1)
        
        try:
            btn_seleccionar = driver.find_element(By.CLASS_NAME, "applyBtn")
            driver.execute_script("arguments[0].click();", btn_seleccionar)
        except Exception:
            pass
        
        select_estado = Select(wait.until(EC.presence_of_element_located((By.ID, "estado"))))
        select_estado.select_by_value("")
        time.sleep(1)
        
        select_patente = Select(wait.until(EC.presence_of_element_located((By.ID, "patente"))))
        opciones_patentes = [opt.get_attribute("value") for opt in select_patente.options if opt.get_attribute("value") != ""]
        print(f"[INFO] Se detectaron {len(opciones_patentes)} patentes en AVO.")

        fecha_hoy = datetime.now().strftime('%Y%m%d_%H%M%S')

        for idx, patente_val in enumerate(opciones_patentes):
            print(f"[INFO] Consultando patente [{idx+1}/{len(opciones_patentes)}]: {patente_val}")
            select_patente = Select(driver.find_element(By.ID, "patente"))
            select_patente.select_by_value(patente_val)
            time.sleep(1)
            
            btn_buscar = driver.find_element(By.CLASS_NAME, "btn-pagar")
            driver.execute_script("arguments[0].click();", btn_buscar)
            time.sleep(3)
            
            if "La búsqueda realizada no arroja resultados" in driver.page_source:
                print(f"[AVISO] Sin registros para patente {patente_val}.")
                continue
            
            try:
                btn_descarga = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "dl-xls"))
                )
                driver.execute_script("arguments[0].click();", btn_descarga)
                time.sleep(4)

                archivos = glob.glob(os.path.join(temp_download_dir, "*.xls*"))
                if archivos:
                    archivo_reciente = max(archivos, key=os.path.getctime)
                    nuevo_nombre = f"AVO_{patente_val}_{fecha_hoy}.xlsx"
                    ruta_final = os.path.join(target_raw_dir, nuevo_nombre)
                    if os.path.exists(ruta_final):
                        os.remove(ruta_final)
                    shutil.move(archivo_reciente, ruta_final)
                    archivos_descargados.append(ruta_final)
                    print(f"[OK] Archivo guardado en crudos: {nuevo_nombre}")
            except Exception as err:
                print(f"[AVISO] Error al descargar Excel para patente {patente_val}: {err}")

        print(f"[COMPLETADO] Extracción AVO finalizada. Archivos generados: {len(archivos_descargados)}")
        return archivos_descargados

    except Exception as e:
        print(f"[ERROR] Fallo durante la extracción de AVO para {client_id}: {e}")
        return archivos_descargados

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        if os.path.exists(temp_download_dir):
            try:
                shutil.rmtree(temp_download_dir)
            except Exception:
                pass


def ejecutar_desde_config():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "config", "clients.json")

    if not os.path.exists(config_path):
        print(f"[ERROR] No se encontró el archivo de configuración en {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        clientes = json.load(f)

    for cliente in clientes:
        if not cliente.get("active", True):
            continue

        if "avo" in cliente.get("services", []):
            client_id = cliente["id"]
            creds = cliente.get("credentials", {})
            rut = creds.get("rut_empresa")
            password = creds.get("password_portal")

            if rut and password:
                extraer_avo(client_id, rut, password, base_dir)
            else:
                print(f"[OMITIDO] Faltan credenciales para el cliente {client_id}")


if __name__ == "__main__":
    ejecutar_desde_config()