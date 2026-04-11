from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from app import db
from app.core.auth.routes import login_required
from app.models.tenant import Subagrupacion
from app.modules.socios.models import Persona
from app.modules.musicos.models import (
    Instrumento, Musico, MusicoSubagrupacion, MusicoInstrumento
)
from app.modules.musicos.forms import (
    MusicoForm, MusicoSubagrupacionForm, MusicoInstrumentoForm
)

musicos_bp = Blueprint('musicos', __name__, url_prefix='/musicos')

def musicos_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.get('user'):
            flash('Debes iniciar sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        if not g.user.tiene_permiso('musicos.ver'):
            flash('No tienes permiso para acceder al módulo de músicos.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)

    return decorated


# ---- Dasboard Músicos -------------------------------------------

@musicos_bp.route('/')
@musicos_required
def index():
    total_musicos = Musico.for_tenant(g.tenant_id).filter_by(estado='activo').count()
    total_subagrupaciones = Subagrupacion.query.filter_by(
        tenant_id=g.tenant_id, activa=True
    ).count()
    total_instrumentos = Instrumento.for_tenant(g.tenant_id).count()

    musicos_recientes = Musico.for_tenant(g.tenant_id).order_by(
        Musico.created_at.desc()
    ).limit(5).all()

    return render_template('musicos/index.html',
                           total_musicos=total_musicos,
                           total_subagrupaciones=total_subagrupaciones,
                           total_instrumentos=total_instrumentos,
                           musicos_recientes=musicos_recientes)


