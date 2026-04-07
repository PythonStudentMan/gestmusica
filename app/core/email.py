"""
Utilidades de email para GestMusica
Todas las funciones de envío pasan por aquí para centralizar
logging, supresión en tests y formato.
"""
import logging
from flask import current_app, render_template, url_for
from flask_mail import Message
from app import mail

logger = logging.getLogger(__name__)

def _send(msg: Message):
    """ Envía un Message de Flask-Mail. En desarrollo/tests lo vuelva en logs """
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        logger.info(
            "EMAIL SUPRIMIDO [%s] -> %s\n%s",
            msg.subject, msg.recipients, msg.body
        )
        return
    mail.send(msg)

def send_invitacion(invitacion):
    """
    Envía el email de invitación con el enlace de activación.

    :param invitacion: instancia de Invitación (con tenant cargado)
    """
    enlace = url_for(
        'auth.aceptar_invitacion',
        token=invitacion.token,
        _external=True,
    )

    msg = Message(
        subject=f'Invitación a {invitacion.tenant.nombre} - GestMusica',
        recipients=[invitacion.email],
    )
    msg.body = render_template(
        'email/invitacion.txt',
        invitacion=invitacion,
        enlace=enlace,
    )
    msg.html = render_template(
        'email/invitacion.html',
        invitacion=invitacion,
        enlace=enlace,
    )
    _send(msg)
    logger.info(
        "Invitación enviada a %s (tenant=%s token=%s)",
        invitacion.email, invitacion.tenant.slug, invitacion.token,
    )