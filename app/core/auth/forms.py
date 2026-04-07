from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
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


class AceptarInvitacionForm(FlaskForm):
    """ Formulario que rellena el usuario al aceptar su invitación """
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    apellidos = StringField('Apellidos', validators=[Length(max=128)])
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(), Length(min=8,
                                           message='La contraseña debe tener al menos 8 caracteres.')],
    )
    password2 = PasswordField(
        'Repite la contraseña',
        validators=[DataRequired(), EqualTo('password', message='Las contrasaeñas no coinciden.')],
    )
    submit = SubmitField('Activar cuenta')