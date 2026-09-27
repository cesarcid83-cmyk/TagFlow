import os
import json

class GestorCredenciales:
    def __init__(self, ruta_archivo=None):
        if ruta_archivo is None:
            directorio_actual = os.path.dirname(os.path.abspath(__file__))
            ruta_archivo = os.path.join(directorio_actual, "clientes.json")
        self.ruta_archivo = ruta_archivo
        self.clientes = self._cargar_configuracion()

    def _cargar_configuracion(self):
        # Si existe un archivo json lo lee, si no, usa el cliente por defecto
        if os.path.exists(self.ruta_archivo):
            try:
                with open(self.ruta_archivo, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AVISO] No se pudo leer {self.ruta_archivo}: {e}")
        
        # Configuración por defecto para automaas
        return {
            "automaas": {
                "rut_empresa": "77123456-7",      # Reemplazar con el RUT real de la empresa
                "password_portal": "tu_password",  # Reemplazar con la clave del portal
                "activo": True
            }
        }

    def listar_clientes_activos(self):
        return [c for c, datos in self.clientes.items() if datos.get("activo", True)]

    def obtener_datos_cliente(self, id_cliente):
        return self.clientes.get(id_cliente, {})