from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import String, Boolean, DateTime, Integer, Text, JSON, ForeignKey, UniqueConstraint
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Usuario(Base):
    __tablename__ = "usuarios"
    usuario = mapped_column(String, primary_key=True)
    nombre = mapped_column(String)
    rol = mapped_column(String)
    password_hash = mapped_column(String, nullable=True)
    activo = mapped_column(Boolean, default=True)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)


class QREmitido(Base):
    __tablename__ = "qr_emitidos"
    token = mapped_column(String, primary_key=True)
    dni_trabajador = mapped_column(String(8))
    nn = mapped_column(String(3))
    producto = mapped_column(String)
    estado = mapped_column(String, default="DISPONIBLE")
    impreso_por = mapped_column(String)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)
    usado_en = mapped_column(DateTime, nullable=True)


class Producto(Base):
    __tablename__ = "productos"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre = mapped_column(String(120), unique=True, nullable=False)
    activo = mapped_column(Boolean, default=True)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)

class Impresora(Base):
    __tablename__ = "impresoras"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre = mapped_column(String(120), unique=True, nullable=False)
    marca = mapped_column(String(20), default="ZEBRA")      # ZEBRA | TSC
    conexion = mapped_column(String(10), default="RED")     # RED | USB (informativo)
    ip = mapped_column(String(64), nullable=False)
    puerto = mapped_column(Integer, default=9100)
    activa = mapped_column(Boolean, default=True)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)


class Trabajador(Base):
    __tablename__ = "trabajadores"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    dni = mapped_column(String(8), unique=True, nullable=False)
    nombre = mapped_column(String, nullable=False)
    apellido_paterno = mapped_column(String, nullable=False)
    apellido_materno = mapped_column(String, nullable=True)
    rol = mapped_column(String, nullable=False)
    num_orden = mapped_column(Integer, unique=True, nullable=False)
    cod_letra = mapped_column(String(4), unique=True, nullable=False)
    activo = mapped_column(Boolean, default=True, nullable=False)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)


class Lote(Base):
    __tablename__ = "lotes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo = mapped_column(String(64), unique=True, nullable=False)
    estado = mapped_column(String(16), nullable=False, default="ABIERTO")
    creado_por = mapped_column(String(128), nullable=True)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)
    cerrado_en = mapped_column(DateTime, nullable=True)
    cerrado_por = mapped_column(String(128), nullable=True)
    reabierto_en = mapped_column(DateTime, nullable=True)
    reabierto_por = mapped_column(String(128), nullable=True)


class ScanEvent(Base):
    __tablename__ = "scan_events"

    token = mapped_column(String(255), primary_key=True)
    dni = mapped_column(String(8), nullable=False)
    user_id = mapped_column(String(128), nullable=True)
    device_id = mapped_column(String(128), nullable=True)
    scanned_at = mapped_column(DateTime, default=datetime.utcnow)
    batch_uuid = mapped_column(String(128), nullable=True)
    session_uuid = mapped_column(String(128), nullable=True)
    raw = mapped_column(JSON, nullable=True)
    lote_id = mapped_column(Integer, ForeignKey("lotes.id"), nullable=True)


class Persona(Base):
    __tablename__ = "personas"
    __table_args__ = (UniqueConstraint("tipo_doc", "nro_doc", name="uq_personas_tipo_nro"),)

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_doc = mapped_column(String(16), nullable=False)
    nro_doc = mapped_column(String(32), nullable=False)
    nombres = mapped_column(String(255), nullable=True)
    apellido_paterno = mapped_column(String(255), nullable=True)
    apellido_materno = mapped_column(String(255), nullable=True)
    fuente = mapped_column(String(32), nullable=True)
    updated_at = mapped_column(DateTime, default=datetime.utcnow)


class VigilanciaVisita(Base):
    __tablename__ = "vigilancia_visitas"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    dni = mapped_column(String(8), nullable=False)
    tipo = mapped_column(String(16), nullable=False)
    nombres = mapped_column(Text, nullable=True)
    apellido_paterno = mapped_column(Text, nullable=True)
    apellido_materno = mapped_column(Text, nullable=True)
    usuario = mapped_column(String(128), nullable=True)
    creado_en = mapped_column(DateTime, default=datetime.utcnow)
