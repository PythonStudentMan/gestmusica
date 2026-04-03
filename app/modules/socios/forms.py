from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, BooleanField, SelectField,
    DecimalField, DateField, SubmitField
)
from wtforms.validators import DataRequired, Optional, Email, Length
from datetime import date

PERIODICIDAD_CHOICES = [
    ('unico', 'Pago Único'),
    ('mensual', 'Mensual'),
    ('bimensual', 'Bimensual'),
    ('trimestral', 'Trimestral'),
    ('cuatrimestral', 'Cuatrimestral'),
    ('anual', 'Anual'),
    ('semanal', 'Semanal'),
    ('quincenal', 'Quincenal'),
]

ESTADO_SOCIO_CHOICES = [
    ('activo', 'Activo'),
    ('baja', 'Baja'),
    ('suspendido', 'Suspendido'),
]

METODO_PAGO_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('tarjeta', 'Tarjeta'),
    ('transferencia', 'Transferencia'),
    ('giro', 'Giro domiciliado'),
    ('bizum', 'Bizum'),
]

RELACION_TUTOR_CHOICES = [
    ('padre', 'Padre'),
    ('madre', 'Madre'),
    ('tutor_legal', 'Tutor legal'),
    ('otro', 'Otro'),
]

TIPO_DESCUENTO_CHOICES = [
    ('', 'Sin descuento'),
    ('porcentual', 'Porcentual (%)'),
    ('tarifa_plana', 'Tarifa plana (€)'),
]

class TipoSocioForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    descripcion = TextAreaField('Descripción', validators=[Optional()])
    importe_cuota = DecimalField('Importe Cuota (€)', validators=[DataRequired()],
                                 places=2, default=0)
    periodicidad = SelectField('Periodicidad', choices=PERIODICIDAD_CHOICES,
                               validators=[DataRequired()])
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar')


class PersonaForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    apellidos = StringField('Apellidos', validators=[DataRequired(), Length(max=128)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=255)])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=32)])
    fecha_nacimiento = DateField('Fecha de nacimiento', validators=[Optional()])
    dni = StringField('DNI/NIE', validators=[Optional(), Length(max=16)])
    submit = SubmitField('Guardar')


class SocioForm(FlaskForm):
    numero_socio = StringField('Número de socio', validators=[DataRequired(), Length(max=32)])
    tipo_socio_id = SelectField('Tipo de socio', validators=[DataRequired()])
    unidad_familiar_id = SelectField('Unidad familiar', validators=[Optional()])
    es_titular_familiar = BooleanField('Es titular de la unidad familiar')
    fecha_alta = DateField('Fecha de alta', validators=[DataRequired()], default=date.today)
    estado = SelectField('Estado', choices=ESTADO_SOCIO_CHOICES, default='activo')
    submit = SubmitField('Guardar')


class BajaForm(FlaskForm):
    fecha_baja = DateField('Fecha de baja', validators=[DataRequired()], default=date.today)
    submit = SubmitField('Dar de baja')


class CuotaForm(FlaskForm):
    tipo_socio_id = SelectField('Tipo de socio', validators=[DataRequired()])
    descripcion = StringField('Descripción', validators=[DataRequired(), Length(max=255)])
    importe = DecimalField('Importe (€)', validators=[DataRequired()], places=2)
    fecha_inicio = DateField('Fecha inicio', validators=[DataRequired()])
    fecha_fin = DateField('Fecha fin', validators=[DataRequired()])
    activa = BooleanField('Activa', default=True)
    submit = SubmitField('Guardar')


class PagoReciboForm(FlaskForm):
    fecha_pago = DateField('Fecha de pago', validators=[DataRequired()], default=date.today)
    metodo_pago = SelectField('Método de pago', choices=METODO_PAGO_CHOICES,
                              validators=[DataRequired()])
    descuento = DecimalField('Descuento (€)', validators=[Optional()], places=2, default=0)
    motivo_descuento = StringField('Motivo descuento', validators=[Optional(), Length(max=255)])
    notas = TextAreaField('Notas', validators=[Optional()])
    submit = SubmitField('Registrar pago')


class TutorLegalForm(FlaskForm):
    persona_tutor_id = SelectField('Tutor', validators=[DataRequired()])
    relacion = SelectField('Relación', choices=RELACION_TUTOR_CHOICES,
                           validators=[DataRequired()])
    patria_potestad = BooleanField('Tiene patria potestad', default=True)
    firma_requerida = BooleanField('Firma requerida en documentos', default=True)
    submit = SubmitField('Guardar')


class SociosConfigForm(FlaskForm):
    musicos_pueden_ser_socios = BooleanField('Los músicos pueden ser socios')
    un_socio_por_unidad_familiar = BooleanField('Un solo socio por unidad familiar')
    max_tutores_menor = DecimalField('Máximo de tutores por menor',
                                     validators=[DataRequired()], places=0, default=2)
    descuento_unidad_familiar = BooleanField('Aplicar descuento por unidad familiar')
    tipo_descuento_escuela = SelectField('Tipo de descuento en escuela',
                                         choices=TIPO_DESCUENTO_CHOICES,
                                         validators=[Optional()])
    valor_descuento_escuela = DecimalField('Valor del descuento', validators=[Optional()],
                                           places=2, default=0)
    submit = SubmitField('Guardar configuración')