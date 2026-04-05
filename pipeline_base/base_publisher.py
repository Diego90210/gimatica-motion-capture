#!/usr/bin/env python3
"""
Base Publisher Module - Pipeline Base Layer 1
Integra los tres anteriores, publica JSON estándar por UDP a localhost:5005
"""

import json
import time
import socket
import threading
from typing import Dict, Callable
import logging
import sys
import os

# Agregar directorio actual al path para importar módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from serial_reader import SerialReader, create_mock_reader
from madgwick_filter import FilterManager
from segment_mapper import SegmentMapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BasePublisher:
    """Publicador principal que integra lectura serial, filtrado y mapeo"""
    
    def __init__(self, port: str = 'COM3', baudrate: int = 921600, 
                 udp_host: str = 'localhost', udp_port: int = 5005,
                 mock_mode: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.mock_mode = mock_mode
        
        # Componentes del pipeline
        self.serial_reader = None
        self.filter_manager = FilterManager(beta=0.1, sample_freq=20.0)
        self.segment_mapper = SegmentMapper()
        
        # UDP socket para publicación
        self.udp_socket = None
        self.is_running = False
        
        # Estadísticas
        self.stats = {
            'messages_sent': 0,
            'sensors_active': set(),
            'last_message_time': None,
            'errors': 0
        }
    
    def initialize(self) -> bool:
        """Inicializa todos los componentes del pipeline"""
        try:
            # Inicializar lector serial
            if self.mock_mode:
                logger.info("Modo simulación activado")
                self.serial_reader = create_mock_reader()
            else:
                self.serial_reader = SerialReader(self.port, self.baudrate)
            
            if not self.serial_reader.connect():
                logger.error("No se pudo conectar al lector serial")
                return False
            
            # Añadir callback para procesar datos
            self.serial_reader.add_callback(self._process_sensor_data)
            
            # Inicializar socket UDP
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logger.info(f"Socket UDP creado para {self.udp_host}:{self.udp_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando publicador: {e}")
            return False
    
    def start(self):
        """Inicia el pipeline completo"""
        if not self.initialize():
            return False
        
        self.is_running = True
        
        # Iniciar lectura serial
        self.serial_reader.start_reading()
        
        # Iniciar hilo de estadísticas
        stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        stats_thread.start()
        
        logger.info("Pipeline Base iniciado correctamente")
        logger.info(f"Publicando a UDP {self.udp_host}:{self.udp_port}")
        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Deteniendo pipeline...")
            self.stop()
    
    def stop(self):
        """Detiene todos los componentes"""
        self.is_running = False
        
        if self.serial_reader:
            self.serial_reader.disconnect()
        
        if self.udp_socket:
            self.udp_socket.close()
        
        self._print_final_stats()
        logger.info("Pipeline detenido")
    
    def _process_sensor_data(self, data: Dict):
        """Procesa datos crudos del sensor y publica JSON estándar"""
        try:
            mac_address = data.get('mac')
            raw_data = data.get('raw_data', {})
            timestamp = data.get('timestamp', time.time() * 1000)
            
            if not mac_address:
                logger.warning("Datos sin dirección MAC")
                return
            
            # Obtener nombre del segmento
            segment_name = self.segment_mapper.get_segment(mac_address)
            if not segment_name:
                logger.debug(f"MAC no mapeada: {mac_address}")
                return
            
            # Extraer datos del IMU
            ax = raw_data.get('ax', 0)
            ay = raw_data.get('ay', 0) 
            az = raw_data.get('az', 0)
            gx = raw_data.get('gx', 0)
            gy = raw_data.get('gy', 0)
            gz = raw_data.get('gz', 0)
            mx = raw_data.get('mx')
            my = raw_data.get('my')
            mz = raw_data.get('mz')
            
            # Aplicar filtro Madgwick
            q = self.filter_manager.update_filter(
                mac_address, ax, ay, az, gx, gy, gz, mx, my, mz
            )
            
            # Obtener ángulos de Euler
            roll, pitch, yaw = self.filter_manager.get_euler_angles(mac_address)
            
            # Construir JSON estándar
            standard_json = {
                "id": mac_address,
                "ts": int(timestamp),
                "segment": segment_name,
                "qw": float(q[0]),
                "qx": float(q[1]),
                "qy": float(q[2]),
                "qz": float(q[3]),
                "roll": round(roll, 2),
                "pitch": round(pitch, 2),
                "yaw": round(yaw, 2)
            }
            
            # Publicar por UDP
            self._publish_udp(standard_json)
            
            # Actualizar estadísticas
            self.stats['messages_sent'] += 1
            self.stats['sensors_active'].add(segment_name)
            self.stats['last_message_time'] = time.time()
            
        except Exception as e:
            logger.error(f"Error procesando datos del sensor: {e}")
            self.stats['errors'] += 1
    
    def _publish_udp(self, data: Dict):
        """Publica datos por UDP"""
        try:
            json_str = json.dumps(data, separators=(',', ':'))
            
            # Enviar por UDP
            self.udp_socket.sendto(
                json_str.encode('utf-8'),
                (self.udp_host, self.udp_port)
            )
            
        except Exception as e:
            logger.error(f"Error publicando UDP: {e}")
            self.stats['errors'] += 1
    
    def _stats_loop(self):
        """Bucle de estadísticas cada 10 segundos"""
        while self.is_running:
            time.sleep(10)
            self._print_stats()
    
    def _print_stats(self):
        """Imprime estadísticas actuales"""
        active_sensors = len(self.stats['sensors_active'])
        messages_per_sec = self.stats['messages_sent'] / 10.0  # Últimos 10 segundos
        
        logger.info(f"Stats: {active_sensors} sensores activos, "
                   f"{messages_per_sec:.1f} msg/s, "
                   f"{self.stats['errors']} errores totales")
    
    def _print_final_stats(self):
        """Imprime estadísticas finales"""
        print(f"\n=== Estadísticas Finales ===")
        print(f"Total mensajes enviados: {self.stats['messages_sent']}")
        print(f"Total errores: {self.stats['errors']}")
        print(f"Sensores activos: {len(self.stats['sensors_active'])}")
        print(f"Sensores detectados: {sorted(self.stats['sensors_active'])}")
        
        if self.stats['last_message_time']:
            last_msg = time.strftime('%H:%M:%S', 
                                 time.localtime(self.stats['last_message_time']))
            print(f"Último mensaje: {last_msg}")

def main():
    """Función principal para ejecutar el publicador"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pipeline Base Publisher')
    parser.add_argument('--port', default='COM3', help='Puerto serial')
    parser.add_argument('--baudrate', type=int, default=921600, help='Baudrate')
    parser.add_argument('--udp-host', default='localhost', help='Host UDP')
    parser.add_argument('--udp-port', type=int, default=5005, help='Puerto UDP')
    parser.add_argument('--mock', action='store_true', help='Modo simulación')
    
    args = parser.parse_args()
    
    # Crear y ejecutar publicador
    publisher = BasePublisher(
        port=args.port,
        baudrate=args.baudrate,
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        mock_mode=args.mock
    )
    
    try:
        publisher.start()
    except KeyboardInterrupt:
        print("\nInterrupción recibida")
    finally:
        publisher.stop()

if __name__ == "__main__":
    main()
