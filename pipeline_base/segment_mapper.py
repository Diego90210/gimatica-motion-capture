#!/usr/bin/env python3
"""
Segment Mapper Module - Pipeline Base Layer 1
Carga sensor_map.json, mapea MAC → nombre de segmento
"""

import json
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SegmentMapper:
    """Mapea direcciones MAC a nombres de segmentos corporales"""
    
    def __init__(self, config_file: str = "sensor_map.json"):
        self.config_file = config_file
        self.mac_to_segment = {}
        self.segment_to_mac = {}
        self.load_mapping()
    
    def load_mapping(self):
        """Carga el mapeo desde archivo JSON"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                
                # Construir diccionarios bidireccionales
                self.mac_to_segment = mapping_data
                self.segment_to_mac = {v: k for k, v in mapping_data.items()}
                
                logger.info(f"Mapeo cargado: {len(self.mac_to_segment)} sensores")
                for mac, segment in self.mac_to_segment.items():
                    logger.debug(f"  {mac} -> {segment}")
            else:
                logger.warning(f"Archivo de mapeo no encontrado: {self.config_file}")
                logger.info("Creando mapeo por defecto para pruebas...")
                self._create_default_mapping()
                
        except Exception as e:
            logger.error(f"Error cargando mapeo: {e}")
            logger.info("Creando mapeo por defecto...")
            self._create_default_mapping()
    
    def _create_default_mapping(self):
        """Crea mapeo por defecto para 14 segmentos"""
        default_mapping = {
            "84:CC:A8:12:34:56": "pelvis",
            "84:CC:A8:12:34:57": "lumbar", 
            "84:CC:A8:12:34:58": "thoracic",
            "84:CC:A8:12:34:59": "sternum",
            "84:CC:A8:12:34:60": "right_thigh",
            "84:CC:A8:12:34:61": "left_thigh",
            "84:CC:A8:12:34:62": "right_tibia",
            "84:CC:A8:12:34:63": "left_tibia",
            "84:CC:A8:12:34:64": "right_foot",
            "84:CC:A8:12:34:65": "left_foot",
            "84:CC:A8:12:34:66": "right_upper_arm",
            "84:CC:A8:12:34:67": "left_upper_arm",
            "84:CC:A8:12:34:68": "right_forearm",
            "84:CC:A8:12:34:69": "left_forearm"
        }
        
        self.mac_to_segment = default_mapping
        self.segment_to_mac = {v: k for k, v in default_mapping.items()}
        
        # Guardar mapeo por defecto
        try:
            self.save_mapping()
            logger.info("Mapeo por defecto guardado en sensor_map.json")
        except Exception as e:
            logger.error(f"No se pudo guardar mapeo por defecto: {e}")
    
    def get_segment(self, mac_address: str) -> Optional[str]:
        """Obtiene nombre de segmento desde MAC"""
        return self.mac_to_segment.get(mac_address)
    
    def get_mac(self, segment_name: str) -> Optional[str]:
        """Obtiene MAC desde nombre de segmento"""
        return self.segment_to_mac.get(segment_name)
    
    def is_valid_segment(self, segment: str) -> bool:
        """Verifica si un segmento es válido según el estándar"""
        valid_segments = {
            "pelvis", "lumbar", "thoracic", "sternum",
            "right_thigh", "left_thigh", "right_tibia", "left_tibia",
            "right_foot", "left_foot",
            "right_upper_arm", "left_upper_arm", "right_forearm", "left_forearm"
        }
        return segment in valid_segments
    
    def get_all_segments(self) -> Dict[str, str]:
        """Retorna todo el mapeo MAC -> segmento"""
        return self.mac_to_segment.copy()
    
    def get_mapped_segments(self) -> list:
        """Retorna lista de segmentos mapeados"""
        return list(self.mac_to_segment.values())
    
    def add_mapping(self, mac_address: str, segment_name: str) -> bool:
        """Añade o actualiza un mapeo"""
        if not self.is_valid_segment(segment_name):
            logger.error(f"Segmento inválido: {segment_name}")
            return False
        
        # Validar formato MAC
        if not self._is_valid_mac(mac_address):
            logger.error(f"Formato MAC inválido: {mac_address}")
            return False
        
        self.mac_to_segment[mac_address] = segment_name
        self.segment_to_mac[segment_name] = mac_address
        
        logger.info(f"Mapeo añadido/actualizado: {mac_address} -> {segment_name}")
        return True
    
    def remove_mapping(self, mac_address: str) -> bool:
        """Elimina un mapeo"""
        if mac_address in self.mac_to_segment:
            segment = self.mac_to_segment[mac_address]
            del self.mac_to_segment[mac_address]
            del self.segment_to_mac[segment]
            logger.info(f"Mapeo eliminado: {mac_address} -> {segment}")
            return True
        return False
    
    def save_mapping(self):
        """Guarda el mapeo actual a archivo JSON"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.mac_to_segment, f, indent=2, ensure_ascii=False)
            logger.info(f"Mapeo guardado en {self.config_file}")
        except Exception as e:
            logger.error(f"Error guardando mapeo: {e}")
    
    def _is_valid_mac(self, mac: str) -> bool:
        """Valida formato de dirección MAC"""
        import re
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')
        return bool(mac_pattern.match(mac))
    
    def validate_mapping(self) -> Dict[str, list]:
        """Valida el mapeo completo y retorna problemas"""
        issues = {
            "duplicate_macs": [],
            "duplicate_segments": [],
            "invalid_segments": [],
            "invalid_macs": []
        }
        
        # Verificar MACs duplicadas
        mac_counts = {}
        for mac in self.mac_to_segment.keys():
            mac_counts[mac] = mac_counts.get(mac, 0) + 1
        
        issues["duplicate_macs"] = [mac for mac, count in mac_counts.items() if count > 1]
        
        # Verificar segmentos duplicados
        segment_counts = {}
        for segment in self.mac_to_segment.values():
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
        
        issues["duplicate_segments"] = [seg for seg, count in segment_counts.items() if count > 1]
        
        # Verificar segmentos inválidos
        for segment in self.mac_to_segment.values():
            if not self.is_valid_segment(segment):
                issues["invalid_segments"].append(segment)
        
        # Verificar MACs inválidas
        for mac in self.mac_to_segment.keys():
            if not self._is_valid_mac(mac):
                issues["invalid_macs"].append(mac)
        
        return issues
    
    def print_status(self):
        """Imprime estado actual del mapeo"""
        print(f"\n=== Estado del Segment Mapper ===")
        print(f"Archivo de configuración: {self.config_file}")
        print(f"Total de sensores mapeados: {len(self.mac_to_segment)}")
        
        print("\nMapeo MAC -> Segmento:")
        for mac, segment in sorted(self.mac_to_segment.items()):
            print(f"  {mac} -> {segment}")
        
        # Validar y mostrar problemas
        issues = self.validate_mapping()
        has_issues = any(len(issue_list) > 0 for issue_list in issues.values())
        
        if has_issues:
            print("\n⚠️  Problemas detectados:")
            for issue_type, issue_list in issues.items():
                if issue_list:
                    print(f"  {issue_type}: {issue_list}")
        else:
            print("\n✅ Mapeo válido sin problemas")

if __name__ == "__main__":
    # Prueba del Segment Mapper
    mapper = SegmentMapper()
    
    # Mostrar estado actual
    mapper.print_status()
    
    # Probar añadir nuevo mapeo
    print("\nAñadiendo nuevo sensor...")
    mapper.add_mapping("84:CC:A8:12:34:70", "test_segment")
    
    # Guardar cambios
    mapper.save_mapping()
    
    # Mostrar estado final
    mapper.print_status()
