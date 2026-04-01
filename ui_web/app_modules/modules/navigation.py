SECTION_USERS = "users"
SECTION_LISTAR = "listar"
SECTION_IMPRESION = "impresion"
SECTION_TRABAJADORES = "trabajadores"
SECTION_VIGILANCIA = "vigilancia"
SECTION_IMPRESORAS = "impresoras"
SECTION_REPORTES = "reportes"
SECTION_LOTES = "lotes"
SECTION_CONSULTAS = "consultas"
SECTION_PRODUCTOS = "productos"

SECTION_LABELS = {
    SECTION_USERS: "👥 Usuarios",
    SECTION_LISTAR: "📋 Listar",
    SECTION_IMPRESION: "🖨️ Impresión",
    SECTION_TRABAJADORES: "👤 Trabajadores",
    SECTION_VIGILANCIA: "🛡️ Vigilancia",
    SECTION_IMPRESORAS: "🖨️ Impresoras",
    SECTION_REPORTES: "📊 Reportes",
    SECTION_LOTES: "📦 Lotes",
    SECTION_CONSULTAS: "🔎 Consultas",
    SECTION_PRODUCTOS: "🧾 Productos",
}

SECTION_TITLES = {
    SECTION_USERS: "ADMINISTRACION DE USUARIOS",
    SECTION_LISTAR: "LISTADO DE TRABAJADORES",
    SECTION_IMPRESION: "IMPRESION DE ETIQUETAS",
    SECTION_TRABAJADORES: "TRABAJADORES",
    SECTION_VIGILANCIA: "CONTROL DE VIGILANCIA",
    SECTION_IMPRESORAS: "CONFIGURACION DE IMPRESORAS",
    SECTION_REPORTES: "REPORTES",
    SECTION_LOTES: "GESTION DE LOTES",
    SECTION_CONSULTAS: "CONSULTA POR DNI",
    SECTION_PRODUCTOS: "MANTENIMIENTO DE PRODUCTOS",
}


def label_for_section(section_id: str) -> str:
    return SECTION_LABELS.get(section_id, section_id)


def title_for_section(section_id: str) -> str:
    return SECTION_TITLES.get(section_id, label_for_section(section_id).upper())


def sections_for_role(role: str) -> list[str]:
    role = (role or "").upper()
    if role in ("ROOT", "GERENCIA"):
        return [
            SECTION_USERS,
            SECTION_PRODUCTOS,
            SECTION_LISTAR,
            SECTION_IMPRESION,
            SECTION_TRABAJADORES,
            SECTION_VIGILANCIA,
            SECTION_IMPRESORAS,
            SECTION_REPORTES,
            SECTION_LOTES,
            SECTION_CONSULTAS,
        ]
    if role == "SUPERVISOR":
        return [
            SECTION_LISTAR,
            SECTION_IMPRESION,
            SECTION_TRABAJADORES,
            SECTION_IMPRESORAS,
            SECTION_REPORTES,
            SECTION_LOTES,
            SECTION_CONSULTAS,
        ]
    if role == "VIGILANCIA":
        return [SECTION_VIGILANCIA]
    return [SECTION_IMPRESION]
