r"""
Utilidades para validación de RUT chileno.

Traducido de la librería PHP Derafu\L10n\Cl\Rut\Rut para mantener
compatibilidad exacta con LibreDTE.
"""

from typing import Union, Tuple


class RutValidator:
    r"""
    Validador de RUT chileno que mantiene compatibilidad exacta con la versión PHP.

    Implementa las mismas funciones que Derafu\L10n\Cl\Rut\Rut:
    - format(): Formatear RUT con guión
    - toArray(): Separar número y dígito verificador
    - validate(): Validar RUT usando algoritmo oficial
    """

    @staticmethod
    def format(rut: Union[str, int]) -> str:
        """
        Formatea un RUT agregando el guión separador.

        Equivale a Rut::format() en PHP.

        Args:
            rut: RUT como string o entero

        Returns:
            RUT formateado como "12345678-9"

        Examples:
            >>> RutValidator.format("123456789")
            "12345678-9"
            >>> RutValidator.format(123456789)
            "12345678-9"
        """
        # Convertir a string y limpiar
        rut_str = str(rut).strip().upper().replace('-', '').replace('.', '')

        # Verificar que no esté vacío
        if not rut_str:
            raise ValueError(f"RUT inválido: {rut}")

        # Verificar longitud mínima (al menos 2 caracteres: número + DV)
        if len(rut_str) < 2:
            raise ValueError(f"RUT inválido: {rut}")

        # Verificar longitud máxima (máximo 9 caracteres: 8 números + DV)
        if len(rut_str) > 9:
            raise ValueError(f"RUT inválido: {rut}")

        # Validar que solo contenga números y K en la posición final
        numero_parte = rut_str[:-1]
        dv_parte = rut_str[-1]

        # Verificar que la parte numérica solo contenga dígitos
        if not numero_parte.isdigit():
            raise ValueError(f"RUT inválido: {rut}")

        # Verificar que el DV sea dígito o K
        if not (dv_parte.isdigit() or dv_parte == 'K'):
            raise ValueError(f"RUT inválido: {rut}")

        # Formatear con guión
        return f"{numero_parte}-{dv_parte}"

    @staticmethod
    def to_array(rut: Union[str, int]) -> Tuple[int, str]:
        """
        Separa un RUT en número y dígito verificador.

        Equivale a Rut::toArray() en PHP.

        Args:
            rut: RUT como string o entero

        Returns:
            Tupla con (número_como_int, dv_como_string)

        Examples:
            >>> RutValidator.to_array("12345678-9")
            (12345678, "9")
            >>> RutValidator.to_array("12345678K")
            (12345678, "K")
        """
        # Formatear para asegurar consistencia
        formatted = RutValidator.format(rut)

        # Separar por guión
        parts = formatted.split('-')
        numero = int(parts[0])
        dv = parts[1]

        return (numero, dv)

    @staticmethod
    def validate(rut: Union[str, int]) -> bool:
        """
        Valida un RUT usando el algoritmo oficial chileno.

        Equivale a Rut::validate() en PHP.

        Args:
            rut: RUT a validar

        Returns:
            True si el RUT es válido, False en caso contrario

        Examples:
            >>> RutValidator.validate("11111111-1")
            True
            >>> RutValidator.validate("12345678-9")
            False
        """
        try:
            numero, dv_actual = RutValidator.to_array(rut)

            # Calcular dígito verificador esperado
            dv_esperado = RutValidator._calcular_dv(numero)

            return dv_actual.upper() == dv_esperado.upper()

        except (ValueError, IndexError):
            return False

    @staticmethod
    def _calcular_dv(numero: int) -> str:
        """
        Calcula el dígito verificador de un RUT.

        Implementa el algoritmo oficial chileno:
        1. Multiplicar cada dígito por la secuencia 2,3,4,5,6,7,2,3,4...
        2. Sumar todos los productos
        3. Calcular 11 - (suma % 11)
        4. Si resultado es 11 → 0, si es 10 → K

        Args:
            numero: Número del RUT (sin dígito verificador)

        Returns:
            Dígito verificador como string ("0"-"9" o "K")
        """
        # Convertir número a string y revertir para iterar desde la derecha
        digitos = str(numero)[::-1]

        # Secuencia de multiplicadores
        multiplicadores = [2, 3, 4, 5, 6, 7]

        suma = 0
        for i, digito in enumerate(digitos):
            multiplicador = multiplicadores[i % 6]
            suma += int(digito) * multiplicador

        # Calcular dígito verificador
        resto = suma % 11
        dv = 11 - resto

        if dv == 11:
            return "0"
        elif dv == 10:
            return "K"
        else:
            return str(dv)