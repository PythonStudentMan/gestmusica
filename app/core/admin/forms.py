from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, TextAreaField,
    SelectMultipleField, SelectField, SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, Optional
from wtforms.widgets import ListWidget, CheckboxInput

PERMISOS_DISPONIBLES = [
    ('socios.ver', 'Socios - Ver'),
    ('socios.crear', 'Socios - Crear'),
    ('socios.editar', 'Socios - Editar'),
    ('socios.eliminar', 'Socios - Eliminar'),

    ('musicos.ver_propio', 'Músicos - Ver ficha propia'),
    ('musicos.editar_propio', 'Músicos - Editar ficha propia'),
    ('musicos.ver_seccion', 'Músicos - Ver sección'),
    ('musicos.ver_todos', 'Músivos - Ver todos'),
    ('musicos.crear', 'Músicos - Crear'),
    ('musicos.editar', 'Músicos - Editar'),
    ('musicos.baja', 'Músicos - Dar de baja'),
    ('musicos.asignar', 'Músicos - Asignar a subagrupaciones'),

    ('eventos.ver', 'Eventos - Ver'),
    ('eventos.crear', 'Eventos - Crear'),
    ('eventos.editar', 'Eventos - Editar'),
    ('eventos.eliminar', 'Eventos - Eliminar'),

    ('admin.usuarios', 'Admin - Gestión de usuarios'),
    ('admin.roles', 'Admin - Gestión de roles'),
]


class UsuarioForm(FlaskForm):
    nombre = StringField(
        'Nombre',
        validators=[DataRequired(), Length(max=128)],
    )
    apellidos = StringField(
        'Apellidos',
        validators=[Optional(), Length(max=128)],
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    password = PasswordField(
        'Contraseña',
        validators=[Optional(), Length(min=8)],
        description='Déjalo vacío para NO cambiar la contraseña.',
    )
    activo = BooleanField('Usuario activo', default=True)
    submit = SubmitField('Guardar')


class RolForm(FlaskForm):
    nombre = StringField(
        'Nombre del rol',
        validators=[DataRequired(), Length(max=128)],
    )
    permisos = SelectMultipleField(
        'Permisos',
        choices=PERMISOS_DISPONIBLES,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    submit = SubmitField('Guardar')

class MemberPermisoForm(FlaskForm):
    permiso = SelectField(
        'Permiso',
        choices=PERMISOS_DISPONIBLES,
        validators=[DataRequired()],
    )
    motivo = StringField(
        'Motivo',
        validators=[DataRequired(), Length(max=255)],
        description='Explica brevemente por qué se asigna este permiso extraordinario.',
    )
    submit = SubmitField('Añadir permiso')

class InvitacionForm(FlaskForm):
    """ Formulario para que el admin invita a un nuevo usuario por email """
    email = StringField(
        'Email del invitado',
        validators=[DataRequired(), Email(), Length(max=255)],
        description='Se enviará un enlace de activación a esta dirección.',
    )
    nombre = StringField(
        'Nombre (opcional)',
        validators=[Optional(), Length(max=128)],
        description='Nombre sugerido. El usuario podrá cambiarlo al activar su cuenta.',
    )
    submit = SubmitField('Enviar invitación')



class SubagrupacionForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=255)])
    descripcion = TextAreaField('Descripcion', validators=[Optional()])
    activa = BooleanField('Activa', default=True)
    submit = SubmitField('Guardar')


class InstrumentoForm(FlaskForm):

    FAMILIAS = [
        ('', 'Sin clasificar'),
        ('direccion', 'Dirección Musical'),
        ('viento_madera', 'Viento Madera'),
        ('viento_metal', 'Viento Metal'),
        ('percusion', 'Percusión'),
        ('cuerda_frotada', 'Cuerda Frotada'),
        ('cuerda_pulsada', 'Cuerda Pulsada'),
        ('teclado', 'Teclado'),
        ('voz', 'Voz'),
        ('electronico', 'Electrónico'),
    ]

    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=64)])
    familia = SelectField('Familia', choices=FAMILIAS, validators=[Optional()])
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar')