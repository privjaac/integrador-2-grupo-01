#!/usr/bin/env python
"""
Utilidad de línea de comandos de Django para tareas administrativas.

Este archivo `manage.py` es el punto de entrada principal para tu proyecto Django.
Actúa como un script a través del cual puedes interactuar con tu proyecto.
Por ejemplo, se utiliza para:
1. Levantar el servidor de desarrollo local (`python manage.py runserver`).
2. Crear y aplicar migraciones a la base de datos (`python manage.py makemigrations` / `migrate`).
3. Crear nuevas sub-aplicaciones (`python manage.py startapp {nombre}`).
4. Entrar a una consola interactiva (`python manage.py shell`).
"""
import os
import sys


def main():
    """Ejecuta tareas administrativas."""
    
    # Aquí le indicamos a Django dónde encontrar las configuraciones principales de tu proyecto.
    # En tu caso, le dice que busque dentro de la carpeta 'core' el archivo 'settings.py'.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        # Intenta importar la función de Django encargada de interpretar y ejecutar comandos
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Si Django no está instalado o no tienes activado tu entorno virtual (venv),
        # esta excepción mostrará un error amigable explicando qué pudo salir mal.
        raise ImportError(
            "No se pudo importar Django. ¿Estás seguro de que está instalado y "
            "disponible en tu variable de entorno PYTHONPATH? ¿Olvidaste "
            "activar un entorno virtual?"
        ) from exc
        
    # Toma los argumentos que escribiste en la terminal (ej: 'runserver') 
    # y los ejecuta usando la funcionalidad interna de Django.
    execute_from_command_line(sys.argv)

# === EXPLICACIÓN DE __name__ == '__main__' ===
# En Python, cada archivo tiene una variable secreta o mágica llamada __name__.
# Python le asigna un valor a esta variable dependiendo de cómo se ejecutó el archivo:
#
# 1. Si tú ejecutas este archivo DIRECTAMENTE desde la terminal (ej: python manage.py)
#    Python dice: "Este es el archivo principal", y le asigna a __name__ el valor de un texto: '__main__'.
# 
# 2. PERO si otro archivo estuviera importando este (ej: `import manage`), 
#    Python le asignaría a __name__ el nombre del archivo (es decir, '__name__' valdría 'manage').
#
# Por lo tanto, este 'if' actúa como un seguro:
# Solo ejecutará la función main() SI Y SOLO SI tú ejecutaste manage.py directamente.
if __name__ == '__main__':
    main()
