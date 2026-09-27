import os
import time
import glob
import shutil
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

def extraer_autopase_cliente(id_cliente, rut, password, carpeta_descargas_temp, carpeta_destino_base):
    """Ejecuta la extracción de consumos de Autopase para un cliente en específico."""
    print(f"\n==========================================")
    print(f"[PROCESO] Iniciando extracción para: {id_cliente} (RUT: {rut})")
    print(f"==========================================")

    # Ruta estándar bajo la nueva arquitectura
    carpeta_cliente = os.path.join(carpeta_destino_base, "data", id_cliente, "raw")
    os.makedirs(carpeta_cliente, exist_ok=True)
    os.makedirs(carpeta_descargas_temp, exist_ok=True)

    # Opciones exactamente idénticas a tu script funcional original
    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option('useAutomationExtension', False)
    
    prefs = {
        "download.default_directory": carpeta_descargas_temp,
        "download.prompt_for_download": False
    }
    opciones.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=opciones)
    wait = WebDriverWait(driver, 15)

    try:
        print("[INFO] Abriendo Autopase...")
        driver.get("https://www.autopase.cl/")
        time.sleep(4)  # Esperar a que cargue la página y aparezca el popup

        # Eliminación del modal publicitario con JavaScript (original)
        try:
            driver.execute_script("""
                var modales = document.querySelectorAll('.modal, .modal-backdrop, [role="dialog"], #modalImagen');
                for (var i = 0; i < modales.length; i++) {
                    modales[i].remove();
                }
            """)
            print("[INFO] Popup publicitario eliminado de la pantalla.")
            time.sleep(1)
        except Exception as e_modal:
            print(f"[AVISO] No se encontró modal o ya estaba cerrado: {e_modal}")

        print("[INFO] Iniciando sesión...")
        btn_clientes = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-clientes-desk")))
        driver.execute_script("arguments[0].click();", btn_clientes)
        time.sleep(2)
        
        driver.find_element(By.ID, "sRUT").send_keys(rut)
        driver.find_element(By.ID, "sClave").send_keys(password)
        driver.find_element(By.ID, "Enviar").click()

        print("[INFO] Ingresando al panel de consumos...")
        time.sleep(3)
        driver.get("https://www.autopase.cl/cliente/consumos/consumo_peaje_nofacturado")
        time.sleep(3)

        select_patente = Select(wait.until(EC.presence_of_element_located((By.ID, "patente"))))
        opciones_patentes = [op.text.strip() for op in select_patente.options if op.text.strip() and "Seleccione" not in op.text]
        print(f"[INFO] Se encontraron {len(opciones_patentes)} patentes: {opciones_patentes}")

        fecha_hoy = datetime.now().strftime('%d%m%Y')

        for patente in opciones_patentes:
            print(f"[INFO] Procesando patente: {patente}")
            
            select_patente = Select(driver.find_element(By.ID, "patente"))
            select_patente.select_by_visible_text(patente)
            time.sleep(1)

            driver.find_element(By.XPATH, "//button[text()='Buscar'] | //input[@value='Buscar']").click()
            time.sleep(4)

            try:
                btn_descargar = driver.find_element(By.XPATH, "//button[contains(text(), 'Descargar')] | //a[contains(text(), 'Descargar')]")
                driver.execute_script("arguments[0].click();", btn_descargar)
                print(f"[INFO] Descarga solicitada para {patente}...")
                time.sleep(4)

                archivos = glob.glob(os.path.join(carpeta_descargas_temp, "*.csv"))
                if archivos:
                    archivo_reciente = max(archivos, key=os.path.getctime)
                    nuevo_nombre = f"Autopase_{patente}_{fecha_hoy}.csv"
                    ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
                    
                    if os.path.exists(ruta_final): 
                        os.remove(ruta_final)
                    shutil.move(archivo_reciente, ruta_final)
                    print(f"[ÉXITO] Archivo guardado: {ruta_final}")
            except Exception as e_descarga:
                print(f"[AVISO] Sin registros o error en descarga para {patente}: {e_descarga}")

        print(f"[ÉXITO] Finalizada extracción para {id_cliente}.")

    except Exception as e:
        print(f"[ERROR] Ocurrió un fallo durante el proceso de {id_cliente}: {e}")
        
    finally:
        try:
            driver.quit()
        except:
            pass


def ejecutar_desde_config():
    """Lee config/clients.json y ejecuta la extracción."""
    directorio_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(directorio_base, "config", "clients.json")
    descargas_temp = os.path.join(directorio_base, "temp_downloads")

    if not os.path.exists(config_path):
        print(f"[ERROR] No se encontró el archivo de configuración en {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        clientes = json.load(f)

    for cliente in clientes:
        if not cliente.get("active", True):
            continue

        if "autopase" in cliente.get("services", []):
            cliente_id = cliente["id"]
            creds = cliente.get("credentials", {})
            rut = creds.get("rut_empresa")
            password = creds.get("password_portal")

            if rut and password:
                extraer_autopase_cliente(cliente_id, rut, password, descargas_temp, directorio_base)
            else:
                print(f"[OMITIDO] Faltan datos para el cliente {cliente_id}")


if __name__ == "__main__":
    ejecutar_desde_config()