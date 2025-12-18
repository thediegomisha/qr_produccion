from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import String, Boolean, DateTime, Integer
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

