from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class TenantForm(FlaskForm):
    slug = StringField(
        'Slug (subdominio)',
        validators=[DataRequired(), Length(min=3, max=64)],
        description='Identificador único para la URL. Ej: "banda-san-juan"',
    )
    nombre = StringField(
        'Nombre de la agrupación',
        validators=[DataRequired(), Length(max=255)],
    )
    modo = StringField(
        'Modo',
        validators=[DataRequired()],
        default='saas',
        description='saas (multi-tenant) o standalone',
    )
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar')