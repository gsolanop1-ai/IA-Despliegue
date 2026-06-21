from sqlalchemy import Column, Integer, String, Float, Date, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id               = Column(Integer, primary_key=True, index=True)
    username         = Column(String(50), unique=True, nullable=False, index=True)
    edad             = Column(Integer,  nullable=True)
    sexo             = Column(String(1), nullable=True)
    peso_kg          = Column(Float,    nullable=True)
    altura_cm        = Column(Float,    nullable=True)
    nivel_actividad  = Column(String(20), nullable=True)
    objetivo         = Column(String(20), nullable=True)
    ingredientes_json = Column(Text, nullable=True)  # null = todos disponibles

    planes = relationship("PlanDiario", back_populates="usuario", cascade="all, delete-orphan")

    def tiene_perfil(self):
        return all([self.edad, self.sexo, self.peso_kg, self.altura_cm,
                    self.nivel_actividad, self.objetivo])


class PlanDiario(Base):
    __tablename__ = "planes_diarios"
    __table_args__ = (UniqueConstraint("usuario_id", "fecha", name="uq_usuario_fecha"),)

    id         = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha      = Column(Date, nullable=False, index=True)
    plan_json  = Column(Text, nullable=False)

    usuario = relationship("Usuario", back_populates="planes")
