"""
Configuration Manager - Sistema central de gestión de configuraciones

Proporciona acceso unificado y thread-safe a todas las configuraciones del sistema.
"""

import os
import json
import yaml
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ConfigSource(str, Enum):
    """Fuentes de configuración soportadas"""
    FILE = "file"
    ENVIRONMENT = "environment"
    DICT = "dict"
    REMOTE = "remote"


class ConfigFormat(str, Enum):
    """Formatos de archivo soportados"""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"


@dataclass
class ConfigMetadata:
    """Metadatos de configuración"""
    source: ConfigSource
    file_path: Optional[str] = None
    last_loaded: Optional[str] = None
    last_modified: Optional[str] = None
    checksum: Optional[str] = None
    version: str = "1.0.0"


class ConfigManager:
    """
    Gestor central de configuraciones thread-safe

    Proporciona acceso unificado a configuraciones desde múltiples fuentes
    con caching, validación y recarga automática.
    """

    _instance: Optional['ConfigManager'] = None
    _lock = threading.RLock()

    def __new__(cls) -> 'ConfigManager':
        """Singleton pattern para configuración global"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Inicializa el manager de configuración"""
        if self._initialized:
            return

        self._config_data: Dict[str, Any] = {}
        self._metadata: Dict[str, ConfigMetadata] = {}
        self._watchers: List[callable] = []
        self._cache_enabled = True
        self._auto_reload = False
        self._default_config_paths = [
            "config.yaml",
            "config.json",
            "rypsystems_dte.yaml",
            "rypsystems_dte.json",
            "/etc/rypsystems_dte/config.yaml",
            "~/.rypsystems_dte/config.yaml"
        ]

        # Cargar configuración por defecto
        self._load_default_config()
        self._initialized = True

    def _load_default_config(self):
        """Carga configuración por defecto"""
        default_config = {
            "environment": "development",
            "debug": True,
            "logging": {
                "level": "INFO",
                "format": "json",
                "output": "console"
            },
            "sii": {
                "environment": "certificacion",
                "timeout": 30,
                "retry_attempts": 3
            },
            "features": {
                "validation_strict": True,
                "cache_enabled": True,
                "monitoring_enabled": False
            }
        }

        self._config_data.update(default_config)
        self._metadata["default"] = ConfigMetadata(
            source=ConfigSource.DICT,
            version="1.0.0"
        )

    def load_from_file(self,
                      file_path: Union[str, Path],
                      merge: bool = True) -> bool:
        """
        Carga configuración desde archivo

        Args:
            file_path: Ruta al archivo de configuración
            merge: Si hacer merge con configuración existente

        Returns:
            True si se cargó exitosamente
        """
        try:
            file_path = Path(file_path).expanduser()

            if not file_path.exists():
                return False

            # Detectar formato por extensión
            format_map = {
                '.json': ConfigFormat.JSON,
                '.yaml': ConfigFormat.YAML,
                '.yml': ConfigFormat.YAML,
                '.toml': ConfigFormat.TOML,
                '.ini': ConfigFormat.INI
            }

            file_format = format_map.get(file_path.suffix.lower(), ConfigFormat.YAML)

            # Cargar contenido
            content = file_path.read_text(encoding='utf-8')

            if file_format == ConfigFormat.JSON:
                data = json.loads(content)
            elif file_format in (ConfigFormat.YAML, ConfigFormat.YAML):
                data = yaml.safe_load(content)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")

            # Merge o reemplazar
            with self._lock:
                if merge:
                    self._deep_merge(self._config_data, data)
                else:
                    self._config_data = data

                # Actualizar metadata
                self._metadata[str(file_path)] = ConfigMetadata(
                    source=ConfigSource.FILE,
                    file_path=str(file_path),
                    last_loaded=self._get_timestamp(),
                    last_modified=str(file_path.stat().st_mtime)
                )

            self._notify_watchers()
            return True

        except Exception as e:
            # Usar logging si está disponible
            print(f"Error loading config from {file_path}: {e}")
            return False

    def load_from_environment(self, prefix: str = "RYPSYSTEMS_DTE_") -> bool:
        """
        Carga configuración desde variables de entorno

        Args:
            prefix: Prefijo de las variables de entorno

        Returns:
            True si se cargaron variables
        """
        try:
            env_config = {}

            for key, value in os.environ.items():
                if key.startswith(prefix):
                    # Convertir RYPSYSTEMS_DTE_SII_TIMEOUT a sii.timeout
                    config_key = key[len(prefix):].lower().replace('_', '.')

                    # Intentar convertir tipos
                    if value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                    elif self._is_float(value):
                        value = float(value)

                    self._set_nested_value(env_config, config_key, value)

            if env_config:
                with self._lock:
                    self._deep_merge(self._config_data, env_config)
                    self._metadata["environment"] = ConfigMetadata(
                        source=ConfigSource.ENVIRONMENT,
                        last_loaded=self._get_timestamp()
                    )

                self._notify_watchers()
                return True

            return False

        except Exception as e:
            print(f"Error loading environment config: {e}")
            return False

    def load_from_dict(self, config_dict: Dict[str, Any], merge: bool = True) -> bool:
        """
        Carga configuración desde diccionario

        Args:
            config_dict: Diccionario con configuración
            merge: Si hacer merge con configuración existente

        Returns:
            True si se cargó exitosamente
        """
        try:
            with self._lock:
                if merge:
                    self._deep_merge(self._config_data, config_dict)
                else:
                    self._config_data = config_dict.copy()

                self._metadata["dict"] = ConfigMetadata(
                    source=ConfigSource.DICT,
                    last_loaded=self._get_timestamp()
                )

            self._notify_watchers()
            return True

        except Exception as e:
            print(f"Error loading dict config: {e}")
            return False

    def auto_discover_config(self) -> bool:
        """
        Descubre y carga automáticamente archivos de configuración

        Returns:
            True si encontró y cargó algún archivo
        """
        loaded = False

        for path in self._default_config_paths:
            if self.load_from_file(path, merge=True):
                loaded = True

        # Siempre intentar cargar variables de entorno
        if self.load_from_environment():
            loaded = True

        return loaded

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene valor de configuración usando notación de punto

        Args:
            key: Clave en notación de punto (ej: 'sii.environment')
            default: Valor por defecto si no se encuentra

        Returns:
            Valor de configuración o default
        """
        try:
            with self._lock:
                keys = key.split('.')
                value = self._config_data

                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default

                return value
        except Exception:
            return default

    def set(self, key: str, value: Any) -> bool:
        """
        Establece valor de configuración usando notación de punto

        Args:
            key: Clave en notación de punto
            value: Valor a establecer

        Returns:
            True si se estableció exitosamente
        """
        try:
            with self._lock:
                self._set_nested_value(self._config_data, key, value)

                # Actualizar metadata
                self._metadata["runtime"] = ConfigMetadata(
                    source=ConfigSource.DICT,
                    last_loaded=self._get_timestamp()
                )

            self._notify_watchers()
            return True

        except Exception as e:
            print(f"Error setting config {key}: {e}")
            return False

    def has(self, key: str) -> bool:
        """
        Verifica si existe una clave de configuración

        Args:
            key: Clave en notación de punto

        Returns:
            True si la clave existe
        """
        try:
            with self._lock:
                keys = key.split('.')
                value = self._config_data

                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return False

                return True
        except Exception:
            return False

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Obtiene una sección completa de configuración

        Args:
            section: Nombre de la sección

        Returns:
            Diccionario con la sección o vacío
        """
        value = self.get(section, {})
        return value if isinstance(value, dict) else {}

    def get_all(self) -> Dict[str, Any]:
        """
        Obtiene toda la configuración

        Returns:
            Copia de la configuración completa
        """
        with self._lock:
            return self._config_data.copy()

    def reload(self) -> bool:
        """
        Recarga toda la configuración desde las fuentes originales

        Returns:
            True si se recargó exitosamente
        """
        try:
            # Guardar paths de archivos cargados
            file_paths = [
                meta.file_path for meta in self._metadata.values()
                if meta.source == ConfigSource.FILE and meta.file_path
            ]

            # Limpiar configuración actual
            with self._lock:
                self._config_data.clear()
                self._metadata.clear()

            # Recargar configuración por defecto
            self._load_default_config()

            # Recargar archivos
            for file_path in file_paths:
                self.load_from_file(file_path, merge=True)

            # Recargar variables de entorno
            self.load_from_environment()

            self._notify_watchers()
            return True

        except Exception as e:
            print(f"Error reloading config: {e}")
            return False

    def add_watcher(self, callback: callable):
        """
        Agrega callback que se ejecuta cuando cambia la configuración

        Args:
            callback: Función a ejecutar en cambios
        """
        if callback not in self._watchers:
            self._watchers.append(callback)

    def remove_watcher(self, callback: callable):
        """
        Remueve callback de watchers

        Args:
            callback: Función a remover
        """
        if callback in self._watchers:
            self._watchers.remove(callback)

    def get_metadata(self) -> Dict[str, ConfigMetadata]:
        """
        Obtiene metadata de configuración

        Returns:
            Diccionario con metadata de todas las fuentes
        """
        with self._lock:
            return self._metadata.copy()

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Hace merge profundo de diccionarios"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _set_nested_value(self, target: Dict[str, Any], key: str, value: Any):
        """Establece valor usando notación de punto"""
        keys = key.split('.')
        current = target

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _is_float(self, value: str) -> bool:
        """Verifica si string puede ser convertido a float"""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _get_timestamp(self) -> str:
        """Obtiene timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat()

    def _notify_watchers(self):
        """Notifica a todos los watchers de cambios"""
        for watcher in self._watchers:
            try:
                watcher(self._config_data.copy())
            except Exception as e:
                print(f"Error in config watcher: {e}")


# Instancia global singleton
_config_manager = ConfigManager()


def get_config(key: str = None, default: Any = None) -> Any:
    """
    Función conveniente para obtener configuración

    Args:
        key: Clave de configuración (opcional)
        default: Valor por defecto

    Returns:
        Valor de configuración o configuración completa si key es None
    """
    if key is None:
        return _config_manager.get_all()
    return _config_manager.get(key, default)


def set_config_source(source_type: str, **kwargs) -> bool:
    """
    Configura fuente de configuración

    Args:
        source_type: Tipo de fuente ('file', 'environment', 'dict')
        **kwargs: Parámetros específicos de la fuente

    Returns:
        True si se configuró exitosamente
    """
    if source_type == "file":
        return _config_manager.load_from_file(kwargs.get("path"), kwargs.get("merge", True))
    elif source_type == "environment":
        return _config_manager.load_from_environment(kwargs.get("prefix", "RYPSYSTEMS_DTE_"))
    elif source_type == "dict":
        return _config_manager.load_from_dict(kwargs.get("config", {}), kwargs.get("merge", True))
    else:
        raise ValueError(f"Tipo de fuente no soportado: {source_type}")


def reload_config() -> bool:
    """
    Recarga toda la configuración

    Returns:
        True si se recargó exitosamente
    """
    return _config_manager.reload()