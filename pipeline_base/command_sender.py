#!/usr/bin/env python3
"""
Command Sender Module - Pipeline Base Layer 1
Envía comandos RESTART/SLEEP/WAKE al ESP32-S3
"""

import serial
import time
import logging
from typing import Optional
import sys
import os

# Agregar directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from serial_reader import SerialReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CommandSender:
    """Envía comandos de control al ESP32-S3 receptor"""
    
    def __init__(self, port: str = 'COM3', baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        
        # Comandos soportados
        self.COMMANDS = {
            'RESTART': 'RESTART',
            'SLEEP': 'SLEEP',
            'WAKE': 'WAKE',
            'STATUS': 'STATUS',
            'CALIBRATE': 'CALIBRATE'
        }
    
    def connect(self) -> bool:
        """Establece conexión serial para comandos"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2
            )
            
            # Esperar a que el ESP32 esté listo
            time.sleep(2)
            
            logger.info(f"Conectado para comandos en {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando para comandos: {e}")
            return False
    
    def disconnect(self):
        """Cierra conexión serial"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Conexión de comandos cerrada")
    
    def send_command(self, command: str, wait_response: bool = True) -> Optional[str]:
        """
        Envía un comando al ESP32-S3
        
        Args:
            command: Comando a enviar (RESTART, SLEEP, WAKE, etc.)
            wait_response: Si esperar respuesta del dispositivo
            
        Returns:
            Respuesta del dispositivo si wait_response=True, None en caso contrario
        """
        if command not in self.COMMANDS:
            logger.error(f"Comando no soportado: {command}")
            logger.info(f"Comandos soportados: {list(self.COMMANDS.keys())}")
            return None
        
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("No hay conexión serial activa")
            return None
        
        try:
            # Enviar comando
            cmd_line = f"{self.COMMANDS[command]}\n"
            self.serial_conn.write(cmd_line.encode('utf-8'))
            self.serial_conn.flush()
            
            logger.info(f"Comando enviado: {command}")
            
            if wait_response:
                # Esperar respuesta
                start_time = time.time()
                response = ""
                
                while time.time() - start_time < 5.0:  # Timeout 5 segundos
                    if self.serial_conn.in_waiting > 0:
                        line = self.serial_conn.readline().decode('utf-8').strip()
                        if line:
                            response += line
                            if response.endswith('OK') or response.endswith('ERROR'):
                                break
                    
                    time.sleep(0.1)
                
                if response:
                    logger.info(f"Respuesta: {response}")
                    return response
                else:
                    logger.warning("Timeout esperando respuesta")
                    return None
            
            return "OK"  # Respuesta por defecto si no se espera respuesta
            
        except Exception as e:
            logger.error(f"Error enviando comando: {e}")
            return None
    
    def restart_system(self) -> bool:
        """Reinicia el sistema ESP32-S3"""
        logger.info("Enviando comando RESTART...")
        response = self.send_command('RESTART')
        
        if response and 'OK' in response:
            logger.info("Sistema reiniciado correctamente")
            return True
        else:
            logger.error("Error reiniciando sistema")
            return False
    
    def sleep_system(self) -> bool:
        """Pone el sistema en modo bajo consumo"""
        logger.info("Enviando comando SLEEP...")
        response = self.send_command('SLEEP')
        
        if response and 'OK' in response:
            logger.info("Sistema en modo SLEEP")
            return True
        else:
            logger.error("Error poniendo sistema en SLEEP")
            return False
    
    def wake_system(self) -> bool:
        """Despierta el sistema del modo bajo consumo"""
        logger.info("Enviando comando WAKE...")
        response = self.send_command('WAKE')
        
        if response and 'OK' in response:
            logger.info("Sistema despertado correctamente")
            return True
        else:
            logger.error("Error despertando sistema")
            return False
    
    def get_status(self) -> Optional[dict]:
        """Obtiene estado del sistema"""
        logger.info("Enviando comando STATUS...")
        response = self.send_command('STATUS')
        
        if response:
            try:
                # Parsear respuesta JSON si viene en formato JSON
                if response.startswith('{'):
                    import json
                    status_data = json.loads(response)
                    logger.info(f"Estado del sistema: {status_data}")
                    return status_data
                else:
                    # Respuesta en texto plano
                    logger.info(f"Estado del sistema: {response}")
                    return {'status': response}
            except Exception as e:
                logger.error(f"Error parseando respuesta STATUS: {e}")
                return None
        else:
            logger.error("No se pudo obtener estado del sistema")
            return None
    
    def calibrate_sensors(self) -> bool:
        """Inicia calibración de sensores"""
        logger.info("Enviando comando CALIBRATE...")
        response = self.send_command('CALIBRATE', wait_response=True)
        
        if response and 'OK' in response:
            logger.info("Calibración iniciada correctamente")
            return True
        else:
            logger.error("Error iniciando calibración")
            return False
    
    def test_connection(self) -> bool:
        """Prueba básica de conexión"""
        if not self.connect():
            return False
        
        try:
            # Enviar comando de prueba
            response = self.send_command('STATUS')
            
            if response:
                logger.info("Conexión testada correctamente")
                return True
            else:
                logger.error("Sin respuesta en prueba de conexión")
                return False
                
        except Exception as e:
            logger.error(f"Error en prueba de conexión: {e}")
            return False
        finally:
            self.disconnect()
    
    def interactive_mode(self):
        """Modo interactivo para enviar comandos manualmente"""
        print("=== Modo Interactivo de Comandos ===")
        print("Comandos disponibles:", list(self.COMMANDS.keys()))
        print("Escriba 'exit' para salir")
        print()
        
        if not self.connect():
            print("No se pudo conectar al dispositivo")
            return
        
        try:
            while True:
                try:
                    command = input("Comando> ").strip().upper()
                    
                    if command == 'EXIT':
                        break
                    
                    if command in self.COMMANDS:
                        self.send_command(command)
                    else:
                        print(f"Comando no reconocido: {command}")
                        print(f"Disponibles: {list(self.COMMANDS.keys())}")
                        
                except KeyboardInterrupt:
                    break
                    
        finally:
            self.disconnect()
            print("Modo interactivo terminado")

def main():
    """Función principal para ejecutar el sender de comandos"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Command Sender para ESP32-S3')
    parser.add_argument('--port', default='COM3', help='Puerto serial')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate')
    parser.add_argument('--command', help='Comando a enviar')
    parser.add_argument('--interactive', action='store_true', help='Modo interactivo')
    
    args = parser.parse_args()
    
    sender = CommandSender(args.port, args.baudrate)
    
    if args.interactive:
        sender.interactive_mode()
    elif args.command:
        sender.connect()
        sender.send_command(args.command)
        sender.disconnect()
    else:
        # Modo por defecto: prueba de conexión
        print("Probando conexión con el ESP32-S3...")
        if sender.test_connection():
            print("✅ Conexión exitosa")
        else:
            print("❌ Error de conexión")

if __name__ == "__main__":
    main()
