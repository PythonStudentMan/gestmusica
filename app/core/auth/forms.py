from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    slug = StringField(
        'Agrupación',
        validators=[DataRequired(), Length(min=2, max=64)],
        render_kw={'placeholder': 'nombre-de-tu-agrupacion'},
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()],
        render_kw={'placeholder': 'tu@email.com'},
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired()],
    )
    remember = BooleanField('Recordarme')
    submit = SubmitField('Entrar')