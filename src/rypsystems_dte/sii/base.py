"""
Módulo base del SII - Clases principales.

Traducción de las clases PHP principales:
- SiiAmbiente (enum)
- Contribuyente (entidad)
- PartyIdentifier (identificador)
"""

from enum import IntEnum
from typing import Optional, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from .utils import RutValidator


class SiiAmbiente(IntEnum):
    """
    Enum del ambiente del SII cuando está disponible más de uno.

    Traducción directa del enum PHP SiiAmbiente.
    Permite obtener datos asociados al ambiente como el nombre del
    servidor o armar una URL.
    """

    # Ambiente de producción en el SII
    PRODUCCION = 0

    # Ambiente de certificación/pruebas en el SII
    CERTIFICACION = 1

    def is_certificacion(self) -> bool:
        """
        Indica si el ambiente es el de certificación.

        Returns:
            True si es certificación, False si es producción
        """
        return self == SiiAmbiente.CERTIFICACION

    def get_servidor(self, tipo: str = "default") -> str:
        """
        Entrega el servidor del SII según el tipo solicitado.

        Args:
            tipo: Tipo de servidor que se está solicitando

        Returns:
            Nombre del servidor al que se debe conectar en el SII
        """
        # Servidores por defecto para cada ambiente
        servidores_config = {
            "default": {
                0: "palena",    # PRODUCCION
                1: "maullin",   # CERTIFICACION
            },
            "www4": {
                0: "www4",      # PRODUCCION
                1: "www4c",     # CERTIFICACION
            },
        }

        servidores = servidores_config.get(tipo, servidores_config["default"])
        return servidores[self.value]

    def get_wsdl(self, servicio: str) -> str:
        """
        Entrega la URL de un WSDL según su servicio.

        Args:
            servicio: El servicio para el que se desea su WSDL

        Returns:
            WSDL del servicio si fue encontrado o el WSDL por defecto
        """
        # URLs de los WSDL de diferentes servicios del SII
        wsdl_urls = {
            "default": "https://{}.sii.cl/DTEWS/{}.jws?WSDL",
            "QueryEstDteAv": "https://{}.sii.cl/DTEWS/services/{}?WSDL",
            "wsDTECorreo": "https://{}.sii.cl/DTEWS/services/{}?WSDL",
        }

        wsdl_template = wsdl_urls.get(servicio, wsdl_urls["default"])
        servidor = self.get_servidor()

        return wsdl_template.format(servidor, servicio)

    def get_url(self, recurso: str) -> str:
        """
        Entrega la URL de un recurso en el SII según el ambiente.

        Args:
            recurso: Recurso del sitio de SII que se desea su URL

        Returns:
            URL del recurso solicitado
        """
        if recurso == "/anulacionMsvDteInternet":
            servidor = self.get_servidor("www4")
        else:
            servidor = self.get_servidor()

        return f"https://{servidor}.sii.cl{recurso}"


class PartyIdentifier(BaseModel):
    """
    Entidad para representar el identificador único de un participante.

    Traducción directa de la clase PHP PartyIdentifier.
    """

    # Mapa de identificadores de esquema a su nombre
    SCHEME_NAMES: Dict[str, str] = {
        "CL-RUT": "Rol Único Tributario (RUT) de Chile",
        "EMAIL": "Correo electrónico",
    }

    # Mapa de identificadores de esquema a la autoridad que lo administra
    AUTHORITIES: Dict[str, str] = {
        "CL-RUT": "CL-SII",
        "EMAIL": "INTERNET",
    }

    scheme_id: str = Field(default="CL-RUT", description="Identificador del esquema del valor")
    value: str = Field(..., description="Valor del identificador único del participante")

    def get_id(self) -> str:
        """
        Obtiene el identificador completo.

        Returns:
            ID en formato 'esquema:valor'
        """
        return f"{self.scheme_id}:{self.value}"

    def get_scheme_id(self) -> str:
        """
        Obtiene el identificador del esquema.

        Returns:
            Identificador del esquema
        """
        return self.scheme_id

    def get_scheme_name(self) -> str:
        """
        Obtiene el nombre del esquema.

        Returns:
            Nombre del esquema o el ID si no se encuentra
        """
        return self.SCHEME_NAMES.get(self.scheme_id, self.scheme_id)

    def get_value(self) -> str:
        """
        Obtiene el valor del identificador.

        Returns:
            Valor del identificador
        """
        return self.value

    def get_authority(self) -> str:
        """
        Obtiene la autoridad que administra el esquema.

        Returns:
            Autoridad del esquema o el ID si no se encuentra
        """
        return self.AUTHORITIES.get(self.scheme_id, self.scheme_id)


class Contribuyente(BaseModel):
    """
    Clase para representar un contribuyente del SII de Chile.

    Traducción directa de la clase PHP Contribuyente.
    Proporciona información básica del contribuyente, como su RUT, razón social,
    giro, entre otros.
    """

    rut: int = Field(..., description="RUT del contribuyente (solo números)")
    dv: str = Field(..., description="Dígito verificador del RUT")
    razon_social: Optional[str] = Field(None, description="Razón social del contribuyente")
    giro: Optional[str] = Field(None, description="Giro comercial del contribuyente")
    actividad_economica: Optional[int] = Field(None, description="Código de actividad económica")
    telefono: Optional[str] = Field(None, description="Teléfono del contribuyente")
    email: Optional[str] = Field(None, description="Correo electrónico del contribuyente")
    direccion: Optional[str] = Field(None, description="Dirección física del contribuyente")
    comuna: Optional[str] = Field(None, description="Comuna de residencia")

    def __init__(
        self,
        rut: Union[str, int],
        razon_social: Optional[str] = None,
        giro: Optional[str] = None,
        actividad_economica: Optional[int] = None,
        telefono: Optional[str] = None,
        email: Optional[str] = None,
        direccion: Optional[str] = None,
        comuna: Optional[str] = None,
        **data: Any,
    ):
        """
        Constructor de la clase Contribuyente.

        Args:
            rut: RUT del contribuyente
            razon_social: Razón social del contribuyente
            giro: Giro comercial del contribuyente
            actividad_economica: Código de actividad económica
            telefono: Teléfono del contribuyente
            email: Correo electrónico del contribuyente
            direccion: Dirección física del contribuyente
            comuna: Comuna de residencia
        """
        # Formatear y validar RUT
        rut_formateado = RutValidator.format(rut)
        rut_numero, rut_dv = RutValidator.to_array(rut_formateado)

        # Validar el RUT
        if not RutValidator.validate(rut_formateado):
            raise ValueError(f"RUT inválido: {rut}")

        # Convertir valores vacíos a None (incluyendo strings con solo espacios)
        razon_social = razon_social.strip() if razon_social and razon_social.strip() else None
        giro = giro.strip() if giro and giro.strip() else None
        telefono = telefono.strip() if telefono and telefono.strip() else None
        email = email.strip() if email and email.strip() else None
        direccion = direccion.strip() if direccion and direccion.strip() else None
        comuna = comuna.strip() if comuna and comuna.strip() else None

        # Llamar al constructor de Pydantic
        super().__init__(
            rut=rut_numero,
            dv=rut_dv,
            razon_social=razon_social,
            giro=giro,
            actividad_economica=actividad_economica,
            telefono=telefono,
            email=email,
            direccion=direccion,
            comuna=comuna,
            **data,
        )

    def get_rut_as_int(self) -> int:
        """
        Obtiene el RUT como entero (solo números).

        Returns:
            RUT como número entero
        """
        return self.rut

    def get_rut(self) -> str:
        """
        Obtiene el RUT formateado con guión.

        Returns:
            RUT en formato "12345678-9"
        """
        return f"{self.rut}-{self.dv}"

    def get_razon_social(self) -> str:
        """
        Obtiene la razón social o el RUT si no hay razón social.

        Returns:
            Razón social o RUT formateado
        """
        return self.razon_social if self.razon_social else self.get_rut()

    def get_giro(self) -> Optional[str]:
        """
        Obtiene el giro comercial.

        Returns:
            Giro comercial o None
        """
        return self.giro

    def get_actividad_economica(self) -> Optional[int]:
        """
        Obtiene el código de actividad económica.

        Returns:
            Código de actividad económica o None
        """
        return self.actividad_economica

    def get_telefono(self) -> Optional[str]:
        """
        Obtiene el teléfono.

        Returns:
            Teléfono o None
        """
        return self.telefono

    def get_email(self) -> Optional[str]:
        """
        Obtiene el correo electrónico.

        Returns:
            Email o None
        """
        return self.email

    def get_direccion(self) -> Optional[str]:
        """
        Obtiene la dirección.

        Returns:
            Dirección o None
        """
        return self.direccion

    def get_comuna(self) -> Optional[str]:
        """
        Obtiene la comuna.

        Returns:
            Comuna o None
        """
        return self.comuna

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )