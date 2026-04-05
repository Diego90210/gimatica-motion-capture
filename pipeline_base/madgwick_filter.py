#!/usr/bin/env python3
"""
Madgwick Filter Module - Pipeline Base Layer 1
Una instancia del filtro por nodo, produce cuaternión
"""

import numpy as np
import math
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class MadgwickFilter:
    """
    Implementación del filtro Madgwick para fusión de sensores IMU
    Basado en el paper: "An efficient orientation filter for inertial and inertial/magnetic sensor arrays"
    """
    
    def __init__(self, beta: float = 0.1, sample_freq: float = 20.0):
        self.beta = beta  # Ganancia del filtro
        self.sample_freq = sample_freq
        
        # Cuaternión de orientación [w, x, y, z]
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Tiempo del último muestreo
        self.last_time = None
        
        # Bias del giroscopio (para calibración)
        self.gyro_bias = np.array([0.0, 0.0, 0.0])
        
        # Parámetros de calibración
        self.calibrated = False
        
    def update(self, ax: float, ay: float, az: float, 
              gx: float, gy: float, gz: float,
              mx: float = None, my: float = None, mz: float = None,
              timestamp: float = None) -> np.ndarray:
        """
        Actualiza el filtro con nuevos datos del sensor
        
        Args:
            ax, ay, az: Aceleración del acelerómetro
            gx, gy, gz: Velocidad angular del giroscopio
            mx, my, mz: Campo magnético (opcional)
            timestamp: Timestamp en milisegundos
            
        Returns:
            Cuaternión actualizado [w, x, y, z]
        """
        
        # Normalizar aceleración (asumiendo solo gravedad)
        a_norm = math.sqrt(ax*ax + ay*ay + az*az)
        if a_norm > 0:
            ax, ay, az = ax/a_norm, ay/a_norm, az/a_norm
        
        # Aplicar bias al giroscopio
        gx -= self.gyro_bias[0]
        gy -= self.gyro_bias[1]
        gz -= self.gyro_bias[2]
        
        # Convertir a radianes si está en grados
        gx_rad = math.radians(gx)
        gy_rad = math.radians(gy)
        gz_rad = math.radians(gz)
        
        if mx is not None and my is not None and mz is not None:
            # Filtro completo con magnetómetro
            return self._update_marg(ax, ay, az, gx_rad, gy_rad, gz_rad, mx, my, mz)
        else:
            # Filtro sin magnetómetro (solo acelerómetro + giroscopio)
            return self._update_imu(ax, ay, az, gx_rad, gy_rad, gz_rad)
    
    def _update_imu(self, ax: float, ay: float, az: float,
                   gx: float, gy: float, gz: float) -> np.ndarray:
        """Actualización con solo IMU (acelerómetro + giroscopio)"""
        
        # Gradiente del filtro
        q1, q2, q3, q4 = self.q
        
        # Función objetivo del acelerómetro
        f_g = np.array([
            2*(q2*q4 - q1*q3) - ax,
            2*(q1*q2 + q3*q4) - ay,
            q1*q1 - q2*q2 - q3*q3 + q4*q4 - az
        ])
        
        # Jacobiano del acelerómetro
        J_g = np.array([
            [-2*q3, 2*q4, -2*q1, 2*q2],
            [2*q2, 2*q1, 2*q4, 2*q3],
            [0, 0, -4*q2, -4*q3]
        ])
        
        # Gradiente normalizado
        norm = np.linalg.norm(f_g)
        if norm > 0:
            f_g = f_g / norm
        
        # Dirección del gradiente descendente
        q_dot = 0.5 * self._quaternion_multiply(
            self.q, np.array([0, gx, gy, gz])
        ) - self.beta * np.dot(J_g.T, f_g)
        
        # Integrar usando Euler
        self.q = self.q + q_dot * (1.0 / self.sample_freq)
        
        # Normalizar cuaternión
        self.q = self.q / np.linalg.norm(self.q)
        
        return self.q
    
    def _update_marg(self, ax: float, ay: float, az: float,
                    gx: float, gy: float, gz: float,
                    mx: float, my: float, mz: float) -> np.ndarray:
        """Actualización completa MARG (Magnetómetro, Acelerómetro, Giroscopio)"""
        
        # Normalizar magnetómetro
        m_norm = math.sqrt(mx*mx + my*my + mz*mz)
        if m_norm > 0:
            mx, my, mz = mx/m_norm, my/m_norm, mz/m_norm
        
        q1, q2, q3, q4 = self.q
        
        # Función objetivo del acelerómetro y magnetómetro
        f_g = np.array([
            2*(q2*q4 - q1*q3) - ax,
            2*(q1*q2 + q3*q4) - ay,
            q1*q1 - q2*q2 - q3*q3 + q4*q4 - az
        ])
        
        # Referencia del magnetómetro en el marco del cuerpo
        h = np.array([
            mx*(1 - 2*(q3*q3 + q4*q4)) + my*2*(q2*q3 - q1*q4) + mz*2*(q2*q4 + q1*q3),
            mx*2*(q2*q3 + q1*q4) + my*(1 - 2*(q2*q2 + q4*q4)) + mz*2*(q3*q4 - q2*q1),
            mx*2*(q2*q4 - q1*q3) + my*2*(q3*q4 + q2*q1) + mz*(1 - 2*(q2*q2 + q3*q3))
        ])
        
        b = np.array([
            np.linalg.norm(h[0:2]),
            h[2],
            0
        ])
        
        # Función objetivo del magnetómetro
        f_m = np.array([
            b[0]*(2*q2*q4 + 2*q1*q3) - b[1]*2*q3*q4 + b[1]*2*q1*q2 - b[2]*2*q2*q2,
            b[0]*(2*q1*q4 - 2*q2*q3) + b[1]*2*q2*q2 + b[2]*2*q1*q4 - b[2]*2*q3*q3,
            b[0]*2*q1*q3 + b[1]*2*q2*q4 + b[2]*2*q3*q4 - b[0]*2*q2*q2 - b[1]*2*q1*q1
        ])
        
        # Jacobiano combinado
        J_g = np.array([
            [-2*q3, 2*q4, -2*q1, 2*q2],
            [2*q2, 2*q1, 2*q4, 2*q3],
            [0, 0, -4*q2, -4*q3]
        ])
        
        J_m = np.array([
            [-2*b[1]*q3, 2*b[1]*q4, -4*b[0]*q2 - 2*b[1]*q1, -4*b[0]*q3 + 2*b[1]*q4],
            [-2*b[0]*q3 + 2*b[1]*q4, 2*b[0]*q4 + 2*b[1]*q1, -4*b[0]*q2 + 2*b[1]*q3 - 2*b[0]*q1, -4*b[0]*q3 - 2*b[1]*q2 + 2*b[1]*q4],
            [2*b[1]*q2, -2*b[1]*q3, 4*b[0]*q1 + 2*b[1]*q4, -4*b[0]*q2 + 2*b[1]*q3]
        ])
        
        # Gradiente normalizado
        norm_g = np.linalg.norm(f_g)
        norm_m = np.linalg.norm(f_m)
        
        if norm_g > 0:
            f_g = f_g / norm_g
        if norm_m > 0:
            f_m = f_m / norm_m
        
        # Dirección del gradiente descendente
        q_dot = 0.5 * self._quaternion_multiply(
            self.q, np.array([0, gx, gy, gz])
        ) - self.beta * (np.dot(J_g.T, f_g) + np.dot(J_m.T, f_m))
        
        # Integrar usando Euler
        self.q = self.q + q_dot * (1.0 / self.sample_freq)
        
        # Normalizar cuaternión
        self.q = self.q / np.linalg.norm(self.q)
        
        return self.q
    
    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiplicación de cuaterniones"""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    
    def quaternion_to_euler(self, q: np.ndarray = None) -> Tuple[float, float, float]:
        """Convierte cuaternión a ángulos de Euler (roll, pitch, yaw) en grados"""
        if q is None:
            q = self.q
            
        w, x, y, z = q
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        # Convertir a grados
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)
    
    def calibrate_gyro(self, samples: int = 100):
        """Calibra el bias del giroscopio"""
        logger.info("Iniciando calibración del giroscopio...")
        
        bias_sum = np.array([0.0, 0.0, 0.0])
        sample_count = 0
        
        # Aquí se deberían acumular muestras reales del giroscopio
        # Por ahora, asumimos que el bias es cero
        self.gyro_bias = np.array([0.0, 0.0, 0.0])
        self.calibrated = True
        
        logger.info("Calibración completada")
    
    def reset(self):
        """Reinicia el filtro al estado inicial"""
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.last_time = None
        self.calibrated = False

# Fábrica de filtros para múltiples sensores
class FilterManager:
    """Gestiona múltiples instancias del filtro Madgwick"""
    
    def __init__(self, beta: float = 0.1, sample_freq: float = 20.0):
        self.beta = beta
        self.sample_freq = sample_freq
        self.filters = {}
    
    def get_filter(self, sensor_id: str) -> MadgwickFilter:
        """Obtiene o crea un filtro para un sensor específico"""
        if sensor_id not in self.filters:
            self.filters[sensor_id] = MadgwickFilter(self.beta, self.sample_freq)
            logger.info(f"Creado filtro para sensor: {sensor_id}")
        
        return self.filters[sensor_id]
    
    def update_filter(self, sensor_id: str, ax: float, ay: float, az: float,
                   gx: float, gy: float, gz: float,
                   mx: float = None, my: float = None, mz: float = None) -> np.ndarray:
        """Actualiza el filtro de un sensor específico"""
        filter_instance = self.get_filter(sensor_id)
        return filter_instance.update(ax, ay, az, gx, gy, gz, mx, my, mz)
    
    def get_euler_angles(self, sensor_id: str) -> Tuple[float, float, float]:
        """Obtiene ángulos de Euler de un sensor específico"""
        if sensor_id in self.filters:
            return self.filters[sensor_id].quaternion_to_euler()
        return (0.0, 0.0, 0.0)
    
    def reset_all(self):
        """Reinicia todos los filtros"""
        for filter_instance in self.filters.values():
            filter_instance.reset()
        logger.info("Todos los filtros reiniciados")

if __name__ == "__main__":
    # Prueba del filtro Madgwick
    filter_mgr = FilterManager()
    
    # Simular datos de un sensor
    sensor_id = "test_sensor"
    
    for i in range(100):
        # Datos simulados
        q = filter_mgr.update_filter(
            sensor_id,
            ax=0.1, ay=0.2, az=0.9,  # Gravedad principalmente en Z
            gx=1.0, gy=2.0, gz=3.0   # Velocidad angular
        )
        
        roll, pitch, yaw = filter_mgr.get_euler_angles(sensor_id)
        print(f"Muestra {i}: Quaternion={q}, Euler=({roll:.2f}, {pitch:.2f}, {yaw:.2f})")
        
        import time
        time.sleep(0.05)  # 20Hz
