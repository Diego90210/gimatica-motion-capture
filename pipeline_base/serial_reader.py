#!/usr/bin/env python3
"""
Serial Reader Module - Pipeline Base Layer 1
Lee puerto COM a 921600 baudios, parsea JSON crudo por MAC
"""

import serial
import json
import time
import threading
from typing import Dict, Callable, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SerialReader:
    def __init__(self, port: str = 'COM3', baudrate: int = 921600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        self.data_callbacks = []
        self.read_thread = None
        
    def add_callback(self, callback: Callable[[Dict], None]):
        """Añade callback para procesar datos recibidos"""
        self.data_callbacks.append(callback)
        
    def connect(self) -> bool:
        """Establece conexión serial"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            logger.info(f"Conectado al puerto {self.port} a {self.baudrate} baudios")
            return True
        except Exception as e:
            logger.error(f"Error conectando al puerto {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Cierra conexión serial"""
        self.is_running = False
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Conexión serial cerrada")
    
    def start_reading(self):
        """Inicia lectura de datos en hilo separado"""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("No hay conexión serial activa")
            return
        
        self.is_running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        logger.info("Lectura serial iniciada")
    
    def _read_loop(self):
        """Bucle principal de lectura"""
        buffer = ""
        
        while self.is_running:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if data:
                        buffer += data
                        
                        # Procesar líneas completas
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            self._process_line(line)
                            
            except UnicodeDecodeError as e:
                logger.warning(f"Error decodificando datos: {e}")
                buffer = ""  # Limpiar buffer en caso de error
            except Exception as e:
                logger.error(f"Error en bucle de lectura: {e}")
                time.sleep(0.01)
    
    def _process_line(self, line: str):
        """Procesa una línea de datos recibida"""
        try:
            # Intentar parsear como JSON
            data = json.loads(line)
            
            # Validar estructura mínima
            if 'id' in data and 'data' in data:
                # Formato esperado: {"id": "MAC", "data": {...}}
                processed_data = {
                    'mac': data['id'],
                    'raw_data': data['data'],
                    'timestamp': time.time() * 1000  # ms
                }
                
                # Notificar a callbacks
                for callback in self.data_callbacks:
                    callback(processed_data)
                    
        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido recibido: {line} - Error: {e}")
        except Exception as e:
            logger.error(f"Error procesando línea: {line} - Error: {e}")
    
    def send_command(self, command: str) -> bool:
        """Envía comando al dispositivo"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                cmd_line = f"{command}\n"
                self.serial_conn.write(cmd_line.encode('utf-8'))
                logger.info(f"Comando enviado: {command}")
                return True
        except Exception as e:
            logger.error(f"Error enviando comando: {e}")
        return False

# Función para pruebas sin hardware
def create_mock_reader():
    """Crea un lector simulado para pruebas"""
    import random
    
    class MockSerialReader:
        def __init__(self):
            self.data_callbacks = []
            self.is_running = False
            
        def add_callback(self, callback):
            self.data_callbacks.append(callback)
            
        def connect(self):
            return True
            
        def disconnect(self):
            self.is_running = False
            
        def start_reading(self):
            self.is_running = True
            import threading
            threading.Thread(target=self._mock_loop, daemon=True).start()
            
        def _mock_loop(self):
            """Simula datos de sensores"""
            mac_addresses = [
                "84:CC:A8:12:34:56",
                "84:CC:A8:12:34:57",
                "84:CC:A8:12:34:58"
            ]
            
            while self.is_running:
                for mac in mac_addresses:
                    mock_data = {
                        'mac': mac,
                        'raw_data': {
                            'ax': random.uniform(-2, 2),
                            'ay': random.uniform(-2, 2),
                            'az': random.uniform(-2, 2),
                            'gx': random.uniform(-250, 250),
                            'gy': random.uniform(-250, 250),
                            'gz': random.uniform(-250, 250),
                            'mx': random.uniform(-100, 100),
                            'my': random.uniform(-100, 100),
                            'mz': random.uniform(-100, 100)
                        },
                        'timestamp': time.time() * 1000
                    }
                    
                    for callback in self.data_callbacks:
                        callback(mock_data)
                        
                time.sleep(0.05)  # 20Hz por sensor
    
    return MockSerialReader()

if __name__ == "__main__":
    # Prueba del lector serial
    reader = SerialReader('COM3')
    
    def data_callback(data):
        print(f"Datos recibidos: {data}")
    
    reader.add_callback(data_callback)
    
    if reader.connect():
        reader.start_reading()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Deteniendo lectura...")
            reader.disconnect()
