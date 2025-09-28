"""
Feature Flags - Sistema de control de características y funcionalidades

Permite habilitar/deshabilitar características dinámicamente sin necesidad
de redeploy, con soporte para rollout gradual y A/B testing.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union, Callable
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict, field_validator


class FeatureStatus(str, Enum):
    """Estados de las características"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ROLLOUT = "rollout"
    EXPERIMENT = "experiment"
    DEPRECATED = "deprecated"


class RolloutStrategy(str, Enum):
    """Estrategias de rollout"""
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    USER_ATTRIBUTE = "user_attribute"
    TIME_BASED = "time_based"
    REGION_BASED = "region_based"


@dataclass
class UserContext:
    """Contexto del usuario para evaluación de features"""
    user_id: Optional[str] = None
    email: Optional[str] = None
    rut: Optional[str] = None
    region: Optional[str] = None
    environment: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


class RolloutRule(BaseModel):
    """Regla de rollout para características"""
    model_config = ConfigDict(extra='allow')

    strategy: RolloutStrategy = Field(description="Estrategia de rollout")
    enabled: bool = Field(default=True, description="Si la regla está habilitada")

    # Configuración de porcentaje
    percentage: Optional[float] = Field(None, description="Porcentaje de usuarios (0-100)")

    # Configuración de lista de usuarios
    user_list: List[str] = Field(default_factory=list, description="Lista de usuarios")
    user_attribute: Optional[str] = Field(None, description="Atributo de usuario a evaluar")
    attribute_values: List[str] = Field(default_factory=list, description="Valores del atributo")

    # Configuración temporal
    start_time: Optional[datetime] = Field(None, description="Inicio del rollout")
    end_time: Optional[datetime] = Field(None, description="Fin del rollout")

    # Configuración regional
    regions: List[str] = Field(default_factory=list, description="Regiones habilitadas")

    @field_validator('percentage')
    @classmethod
    def validate_percentage(cls, v):
        """Valida que el porcentaje esté en rango válido"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return v

    def evaluate(self, context: UserContext) -> bool:
        """
        Evalúa si la regla aplica para el contexto dado

        Args:
            context: Contexto del usuario

        Returns:
            True si la regla aplica
        """
        if not self.enabled:
            return False

        if self.strategy == RolloutStrategy.PERCENTAGE:
            return self._evaluate_percentage(context)
        elif self.strategy == RolloutStrategy.USER_LIST:
            return self._evaluate_user_list(context)
        elif self.strategy == RolloutStrategy.USER_ATTRIBUTE:
            return self._evaluate_user_attribute(context)
        elif self.strategy == RolloutStrategy.TIME_BASED:
            return self._evaluate_time_based()
        elif self.strategy == RolloutStrategy.REGION_BASED:
            return self._evaluate_region_based(context)

        return False

    def _evaluate_percentage(self, context: UserContext) -> bool:
        """Evalúa rollout por porcentaje"""
        if self.percentage is None:
            return False

        # Usar hash del user_id para distribución consistente
        if context.user_id:
            import hashlib
            hash_value = int(hashlib.md5(context.user_id.encode()).hexdigest(), 16)
            user_percentage = (hash_value % 100) + 1
            return user_percentage <= self.percentage

        return False

    def _evaluate_user_list(self, context: UserContext) -> bool:
        """Evalúa rollout por lista de usuarios"""
        if not self.user_list:
            return False

        return (context.user_id in self.user_list or
                context.email in self.user_list or
                context.rut in self.user_list)

    def _evaluate_user_attribute(self, context: UserContext) -> bool:
        """Evalúa rollout por atributo de usuario"""
        if not self.user_attribute or not self.attribute_values:
            return False

        user_value = context.attributes.get(self.user_attribute)
        return str(user_value) in self.attribute_values

    def _evaluate_time_based(self) -> bool:
        """Evalúa rollout basado en tiempo"""
        now = datetime.now(timezone.utc)

        if self.start_time and now < self.start_time:
            return False

        if self.end_time and now > self.end_time:
            return False

        return True

    def _evaluate_region_based(self, context: UserContext) -> bool:
        """Evalúa rollout basado en región"""
        if not self.regions:
            return True  # Sin restricción de región

        return context.region in self.regions


class FeatureConfig(BaseModel):
    """Configuración de una característica específica"""
    model_config = ConfigDict(extra='allow')

    # Identificación
    name: str = Field(description="Nombre de la característica")
    description: Optional[str] = Field(None, description="Descripción de la característica")
    category: Optional[str] = Field(None, description="Categoría de la característica")

    # Estado
    status: FeatureStatus = Field(default=FeatureStatus.DISABLED, description="Estado de la característica")
    default_value: bool = Field(default=False, description="Valor por defecto")

    # Configuración de rollout
    rollout_rules: List[RolloutRule] = Field(default_factory=list, description="Reglas de rollout")

    # Metadatos
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner: Optional[str] = Field(None, description="Propietario de la característica")
    tags: List[str] = Field(default_factory=list, description="Tags para organización")

    # Configuración adicional
    config_values: Dict[str, Any] = Field(default_factory=dict, description="Valores de configuración")

    def is_enabled_for_context(self, context: UserContext) -> bool:
        """
        Evalúa si la característica está habilitada para el contexto dado

        Args:
            context: Contexto del usuario

        Returns:
            True si está habilitada
        """
        if self.status == FeatureStatus.DISABLED:
            return False

        if self.status == FeatureStatus.ENABLED:
            return True

        if self.status == FeatureStatus.DEPRECATED:
            return False

        # Para rollout y experiment, evaluar reglas
        if self.status in (FeatureStatus.ROLLOUT, FeatureStatus.EXPERIMENT):
            for rule in self.rollout_rules:
                if rule.evaluate(context):
                    return True

        return self.default_value

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración

        Args:
            key: Clave del valor
            default: Valor por defecto

        Returns:
            Valor de configuración
        """
        return self.config_values.get(key, default)


class FeatureFlags(BaseModel):
    """
    Sistema de feature flags

    Gestiona múltiples características y su evaluación.
    """
    model_config = ConfigDict(extra='allow')

    # Configuración del sistema
    default_context: UserContext = Field(default_factory=UserContext)
    strict_mode: bool = Field(default=False, description="Modo estricto (fallar en features no definidos)")

    # Features registrados
    features: Dict[str, FeatureConfig] = Field(default_factory=dict, description="Features registrados")

    # Configuración de logging
    log_evaluations: bool = Field(default=False, description="Loggear evaluaciones de features")
    evaluation_callback: Optional[Callable] = Field(None, description="Callback para evaluaciones")

    def register_feature(self,
                        name: str,
                        description: str = None,
                        default_value: bool = False,
                        **kwargs) -> bool:
        """
        Registra una nueva característica

        Args:
            name: Nombre de la característica
            description: Descripción
            default_value: Valor por defecto
            **kwargs: Configuración adicional

        Returns:
            True si se registró exitosamente
        """
        try:
            feature = FeatureConfig(
                name=name,
                description=description,
                default_value=default_value,
                **kwargs
            )

            self.features[name] = feature
            return True

        except Exception as e:
            print(f"Error registering feature {name}: {e}")
            return False

    def enable_feature(self, name: str) -> bool:
        """
        Habilita una característica

        Args:
            name: Nombre de la característica

        Returns:
            True si se habilitó exitosamente
        """
        if name in self.features:
            self.features[name].status = FeatureStatus.ENABLED
            self.features[name].updated_at = datetime.now(timezone.utc)
            return True
        return False

    def disable_feature(self, name: str) -> bool:
        """
        Deshabilita una característica

        Args:
            name: Nombre de la característica

        Returns:
            True si se deshabilitó exitosamente
        """
        if name in self.features:
            self.features[name].status = FeatureStatus.DISABLED
            self.features[name].updated_at = datetime.now(timezone.utc)
            return True
        return False

    def set_feature_rollout(self,
                           name: str,
                           percentage: float,
                           strategy: RolloutStrategy = RolloutStrategy.PERCENTAGE) -> bool:
        """
        Configura rollout gradual de una característica

        Args:
            name: Nombre de la característica
            percentage: Porcentaje de usuarios
            strategy: Estrategia de rollout

        Returns:
            True si se configuró exitosamente
        """
        if name not in self.features:
            return False

        rule = RolloutRule(
            strategy=strategy,
            percentage=percentage,
            enabled=True
        )

        feature = self.features[name]
        feature.status = FeatureStatus.ROLLOUT
        feature.rollout_rules = [rule]
        feature.updated_at = datetime.now(timezone.utc)

        return True

    def is_enabled(self, name: str, context: Optional[UserContext] = None) -> bool:
        """
        Verifica si una característica está habilitada

        Args:
            name: Nombre de la característica
            context: Contexto del usuario (opcional)

        Returns:
            True si está habilitada
        """
        if name not in self.features:
            if self.strict_mode:
                raise ValueError(f"Feature '{name}' not found")
            return False

        eval_context = context or self.default_context
        result = self.features[name].is_enabled_for_context(eval_context)

        # Logging y callback
        if self.log_evaluations:
            print(f"Feature '{name}' evaluated to {result} for context {eval_context}")

        if self.evaluation_callback:
            try:
                self.evaluation_callback(name, result, eval_context)
            except Exception as e:
                print(f"Error in evaluation callback: {e}")

        return result

    def get_feature_config(self, name: str) -> Optional[FeatureConfig]:
        """
        Obtiene la configuración de una característica

        Args:
            name: Nombre de la característica

        Returns:
            Configuración de la característica o None
        """
        return self.features.get(name)

    def list_features(self, status: Optional[FeatureStatus] = None) -> List[str]:
        """
        Lista características registradas

        Args:
            status: Filtrar por estado (opcional)

        Returns:
            Lista de nombres de características
        """
        if status is None:
            return list(self.features.keys())

        return [
            name for name, feature in self.features.items()
            if feature.status == status
        ]

    def get_all_features_status(self, context: Optional[UserContext] = None) -> Dict[str, bool]:
        """
        Obtiene el estado de todas las características

        Args:
            context: Contexto del usuario (opcional)

        Returns:
            Diccionario con estado de todas las características
        """
        eval_context = context or self.default_context
        return {
            name: feature.is_enabled_for_context(eval_context)
            for name, feature in self.features.items()
        }

    def load_from_dict(self, config_dict: Dict[str, Any]) -> bool:
        """
        Carga configuración desde diccionario

        Args:
            config_dict: Diccionario con configuración

        Returns:
            True si se cargó exitosamente
        """
        try:
            for name, feature_data in config_dict.items():
                if isinstance(feature_data, dict):
                    feature = FeatureConfig.model_validate({
                        'name': name,
                        **feature_data
                    })
                    self.features[name] = feature
                else:
                    # Configuración simple (solo boolean)
                    status = FeatureStatus.ENABLED if feature_data else FeatureStatus.DISABLED
                    feature = FeatureConfig(
                        name=name,
                        status=status,
                        default_value=bool(feature_data)
                    )
                    self.features[name] = feature

            return True

        except Exception as e:
            print(f"Error loading features from dict: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte a diccionario

        Returns:
            Diccionario con configuración
        """
        return {
            name: feature.model_dump()
            for name, feature in self.features.items()
        }


# Sistema global de feature flags
_feature_flags: Optional[FeatureFlags] = None


def get_feature_flags() -> FeatureFlags:
    """
    Obtiene el sistema global de feature flags

    Returns:
        Sistema de feature flags
    """
    global _feature_flags

    if _feature_flags is None:
        _feature_flags = FeatureFlags()

        # Cargar features desde variables de entorno
        _load_features_from_environment(_feature_flags)

        # Registrar features por defecto
        _register_default_features(_feature_flags)

    return _feature_flags


def set_feature_flags(flags: FeatureFlags) -> None:
    """
    Establece el sistema global de feature flags

    Args:
        flags: Nuevo sistema de feature flags
    """
    global _feature_flags
    _feature_flags = flags


def get_feature_flag(name: str, context: Optional[UserContext] = None) -> bool:
    """
    Función conveniente para verificar feature flags

    Args:
        name: Nombre de la característica
        context: Contexto del usuario

    Returns:
        True si está habilitada
    """
    return get_feature_flags().is_enabled(name, context)


def enable_feature(name: str) -> bool:
    """
    Función conveniente para habilitar características

    Args:
        name: Nombre de la característica

    Returns:
        True si se habilitó exitosamente
    """
    return get_feature_flags().enable_feature(name)


def disable_feature(name: str) -> bool:
    """
    Función conveniente para deshabilitar características

    Args:
        name: Nombre de la característica

    Returns:
        True si se deshabilitó exitosamente
    """
    return get_feature_flags().disable_feature(name)


def _load_features_from_environment(flags: FeatureFlags) -> None:
    """
    Carga features desde variables de entorno

    Args:
        flags: Sistema de feature flags
    """
    prefix = "RYPSYSTEMS_DTE_FEATURE_"

    for key, value in os.environ.items():
        if key.startswith(prefix):
            feature_name = key[len(prefix):].lower()
            enabled = value.lower() in ('true', '1', 'on', 'yes')

            flags.register_feature(
                name=feature_name,
                description=f"Feature loaded from environment: {key}",
                default_value=enabled
            )

            if enabled:
                flags.enable_feature(feature_name)


def _register_default_features(flags: FeatureFlags) -> None:
    """
    Registra features por defecto del sistema

    Args:
        flags: Sistema de feature flags
    """
    default_features = {
        "strict_validation": {
            "description": "Validación estricta de documentos",
            "default_value": True,
            "category": "validation"
        },
        "enhanced_logging": {
            "description": "Logging mejorado con contexto extendido",
            "default_value": False,
            "category": "logging"
        },
        "performance_monitoring": {
            "description": "Monitoreo de performance en tiempo real",
            "default_value": False,
            "category": "monitoring"
        },
        "cache_optimization": {
            "description": "Optimizaciones de cache avanzadas",
            "default_value": True,
            "category": "performance"
        },
        "retry_improvements": {
            "description": "Mejoras en lógica de reintentos",
            "default_value": True,
            "category": "reliability"
        },
        "beta_features": {
            "description": "Características en beta",
            "default_value": False,
            "category": "experimental"
        }
    }

    for name, config in default_features.items():
        flags.register_feature(name=name, **config)


def load_feature_config_from_dict(config_dict: Dict[str, Any]) -> FeatureFlags:
    """
    Carga configuración de features desde diccionario

    Args:
        config_dict: Diccionario con configuración

    Returns:
        Sistema de feature flags configurado
    """
    flags = FeatureFlags()
    flags.load_from_dict(config_dict)
    return flags