from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


NIVELES = [
    ('', 'Sin especificar'),
    ('basico', 'Básico'),
    ('medio', 'Medio'),
    ('avanzado', 'Avanzado'),
    ('profesional', 'Profesional'),
]

ROLES_SUBAGRUPACION = [
    ('', 'Sin rol específico'),
    ('solista', 'Solista'),
    ('principal', 'Principal'),
    ('tutti', 'Tutti'),
    ('refuerzo', 'Refuerzo'),
    ('director', 'Director'),
    ('subdirector', 'Subdirector'),
]

ESTADOS_MUSICO = [
    ('activo', 'Activo'),
    ('baja_temporal', 'Baja temporal'),
    ('baja_definitiva', 'Baja definitiva'),
    ('excedencia', 'Excedencia'),
]



class MusicoForm(FlaskForm):
    fecha_ingreso = DateField('Fecha de ingreso', validators=[DataRequired()])
    estado = SelectField('Estado', choices=ESTADOS_MUSICO, default='activo')
    observaciones = TextAreaField('Observaciones', validators=[Optional()])
    submit = SubmitField('Guardar')


class MusicoSubagrupacionForm(FlaskForm):
    subagrupacion_id = SelectField('Subagrupacion', validators=[DataRequired()])
    instrumento_id = SelectField('Instrumento', validators=[Optional()])
    rol = SelectField('Rol', choices=ROLES_SUBAGRUPACION, validators=[Optional()])
    fecha_inicio = DateField('Fecha de inicio', validators=[DataRequired()])
    submit = SubmitField('Asignar')


class MusicoInstrumentoForm(FlaskForm):
    instrumento_id = SelectField('Instrumento', validators=[DataRequired()])
    nivel = SelectField('Nivel', choices=NIVELES, validators=[Optional()])
    submit = SubmitField('Añadir habilidad')