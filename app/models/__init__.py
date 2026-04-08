from app.models.tenant import Tenant, TenantConfig, Module, TenantModule, Subagrupacion
from app.models.user import (
    Identity, TenantMember, Session, Role, MemberRole, MemberPermiso, Invitacion
)
from app.modules.socios.models import (
    SociosConfig, UnidadFamiliar, Persona, TutorLegal,
    TipoSocio, Socio, Cuota, Recibo,
)
from app.modules.musicos.models import (
    Instrumento, Musico, MusicoSubagrupacion, MusicoInstrumento
)