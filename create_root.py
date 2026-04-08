""" Script para crear un usuario root """
import os
import sys
from getpass import getpass

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import Identity

app = create_app()

def create_root_user():
    with app.app_context():
        print("\n" + "=" * 50)
        print("CREACIÓN DE USUARIO ROOT - GestMusica")
        print("=" * 50 + "\n")

        email = input("Email: ").strip().lower()

        # Verificar si ya existe
        existing = Identity.query.filter_by(email=email).first()
        if existing:
            if existing.is_root:
                print(f"\n El usuario {email} ya es root.")
            else:
                respuesta = input(f"\n Ya existe un usuario con email {email}. ¿Convertirlo a root? (s/n): ")
                if respuesta.lower() == 's':
                    existing.is_root = True
                    db.session.commit()
                    print(f"\n Usuario {email} convertido a root correctamente.")
            return

        nombre = input("Nombre: ").strip()
        apellidos = input("Apellidos (opcional): ").strip() or None

        password = getpass("Contraseña: ")
        password2 = getpass("Repetir contraseña: ")

        if password != password2:
            print("\n Las contraseñas no coinciden.")
            return

        if len(password) < 8:
            print("\n La contraseña debe tener al menos 8 caracteres.")
            return

        # Crear usuario root
        root = Identity(
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            activo=True,
            is_root=True,
        )
        root.set_password(password)

        db.session.add(root)
        db.session.commit()

        print("\n" + "=" * 50)
        print(f" Usuario root '{email}' creado correctamente.")
        print("=" * 50 + "\n")

if __name__ == '__main__':
    create_root_user()