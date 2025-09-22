"""Declarative base compartida para los modelos de la aplicación."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

__all__ = ["Base"]
