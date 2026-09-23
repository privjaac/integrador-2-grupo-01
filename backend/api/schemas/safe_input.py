"""Validación compartida para los DTO de escritura de la API."""

from html import unescape

from pydantic import BaseModel, field_validator


class SafeInputModel(BaseModel):
    @field_validator('*', mode='before')
    @classmethod
    def reject_html_input(cls, value, info):
        if not isinstance(value, str) or info.field_name == 'password':
            return value
        if info.field_name in {
            'name', 'first_name', 'last_name', 'username', 'city',
            'document_type', 'document_number', 'plan', 'entity_type',
            'new_cupe', 'reason',
        } and not value.strip():
            raise ValueError('El campo no puede estar vacío')
        decoded = value
        for _ in range(3):
            expanded = unescape(decoded)
            if expanded == decoded:
                break
            decoded = expanded
        if '<' in decoded or '>' in decoded:
            raise ValueError('No se permiten etiquetas HTML en este campo')
        if any(ord(char) < 32 and char not in '\t\n\r' for char in decoded):
            raise ValueError('El campo contiene caracteres de control no permitidos')
        return value

    @field_validator('password', check_fields=False)
    @classmethod
    def validate_password_bytes(cls, value):
        if value is not None and len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña no puede superar 72 bytes en UTF-8')
        return value
