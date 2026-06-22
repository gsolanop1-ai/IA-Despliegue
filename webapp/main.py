"""
Backend FastAPI — NutriPerú
===========================
Expone el motor de IA (ai_engine.py) como API REST y sirve el frontend.

Rutas de la aplicación:
  /            → index.html   (login)
  /perfil      → perfil.html  (formulario de perfil)
  /ingredientes→ ingredientes.html (selección de ingredientes)
  /plan        → plan.html    (plan del día)
  /admin       → admin.html   (panel académico)

Endpoints del panel académico — corresponden a celdas del notebook:
  /api/admin/stats   → EDA del dataset          (Celdas 1-3)
  /api/admin/kmeans  → K-Means + PCA 2D         (Celda 8)
  /api/admin/vve     → Suite VV&E con 4 perfiles (Celda 14)
"""

import json
import threading
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from .models import Usuario, PlanDiario
from . import ai_engine
from .ai_engine import PerfilUsuario, generar_plan_completo

Base.metadata.create_all(bind=engine)

# Caché en memoria para resultados estáticos (dataset no cambia en runtime)
_cache_stats = None
_cache_kmeans = None
_cache_vve = None


def _precomputar_admin():
    """Calcula stats, K-Means y VV&E en background para que el panel admin
    no espere en la primera carga. Idempotente: si el caché ya existe, no recalcula."""
    global _cache_stats, _cache_kmeans, _cache_vve
    try:
        if _cache_stats is None:
            _cache_stats = _calcular_stats()
        if _cache_kmeans is None:
            _cache_kmeans = _calcular_kmeans()
        if _cache_vve is None:
            _cache_vve = _calcular_vve()
    except Exception as e:
        print(f"[warmup] Error precomputando admin: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lanzar warm-up en un thread para no bloquear el arranque
    threading.Thread(target=_precomputar_admin, daemon=True).start()
    yield


app = FastAPI(title="NutriPerú", version="1.0", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── HTML routes ───────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/perfil")
def perfil_page():
    return FileResponse(STATIC_DIR / "perfil.html")

@app.get("/plan")
def plan_page():
    return FileResponse(STATIC_DIR / "plan.html")

@app.get("/ingredientes")
def ingredientes_page():
    return FileResponse(STATIC_DIR / "ingredientes.html")

@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


# ── Schemas ───────────────────────────────────────────────────
class EntrarRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=30)

class PerfilRequest(BaseModel):
    edad:            int   = Field(..., ge=10, le=100)
    sexo:            str   = Field(..., pattern="^[MF]$")
    peso_kg:         float = Field(..., ge=30, le=250)
    altura_cm:       float = Field(..., ge=100, le=230)
    nivel_actividad: str
    objetivo:        str

class IngredientesRequest(BaseModel):
    ingredientes: list[str]


# ── Helpers ───────────────────────────────────────────────────
def get_usuario_or_404(db: Session, username: str) -> Usuario:
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    return user

def usuario_a_perfil(user: Usuario) -> PerfilUsuario:
    return PerfilUsuario(
        edad=user.edad, sexo=user.sexo,
        peso_kg=user.peso_kg, altura_cm=user.altura_cm,
        nivel_actividad=user.nivel_actividad, objetivo=user.objetivo
    )

def ingredientes_ultimos_dias(db: Session, usuario_id: int, dias: int = 2) -> set:
    """Retorna nombres de ingredientes usados en los últimos `dias` días (excluye snack)."""
    desde = date.today() - timedelta(days=dias)
    planes = db.query(PlanDiario).filter(
        PlanDiario.usuario_id == usuario_id,
        PlanDiario.fecha >= desde,
        PlanDiario.fecha < date.today()
    ).all()
    usados = set()
    for p in planes:
        data = json.loads(p.plan_json)
        for comida in data.get('comidas', []):
            if comida.get('comida') != 'snack':
                for ing in comida.get('plan', []):
                    usados.add(ing['nombre'])
    return usados


# ── API endpoints ─────────────────────────────────────────────
@app.post("/api/usuario/entrar")
def entrar(req: EntrarRequest, db: Session = Depends(get_db)):
    """Entra con username. Crea el usuario si no existe."""
    username = req.username.strip().lower()
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user:
        user = Usuario(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {
        "username":      user.username,
        "tiene_perfil":  user.tiene_perfil(),
        "nuevo":         not user.tiene_perfil(),
    }


@app.get("/api/usuario/{username}/perfil")
def get_perfil(username: str, db: Session = Depends(get_db)):
    user = get_usuario_or_404(db, username)
    return {
        "username":       user.username,
        "edad":           user.edad,
        "sexo":           user.sexo,
        "peso_kg":        user.peso_kg,
        "altura_cm":      user.altura_cm,
        "nivel_actividad": user.nivel_actividad,
        "objetivo":       user.objetivo,
        "tiene_perfil":   user.tiene_perfil(),
    }


@app.post("/api/usuario/{username}/perfil")
def guardar_perfil(username: str, req: PerfilRequest, db: Session = Depends(get_db)):
    user = get_usuario_or_404(db, username)
    user.edad            = req.edad
    user.sexo            = req.sexo
    user.peso_kg         = req.peso_kg
    user.altura_cm       = req.altura_cm
    user.nivel_actividad = req.nivel_actividad
    user.objetivo        = req.objetivo
    db.commit()
    return {"ok": True, "username": user.username}


def _calcular_stats():
    import pandas as pd
    df = ai_engine.df_ingredientes.copy()
    nums = ['calorias', 'proteina_g', 'carbohidratos_g', 'grasa_g', 'fibra_g', 'grasa_saturada_g']
    for col in nums:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    por_cat = {}
    for cat, grp in df.groupby('categoria'):
        por_cat[cat] = {
            'count':       int(len(grp)),
            'avg_kcal':    round(float(grp['calorias'].mean()), 1),
            'avg_proteina':round(float(grp['proteina_g'].mean()), 1),
            'avg_carbos':  round(float(grp['carbohidratos_g'].mean()), 1),
            'avg_grasa':   round(float(grp['grasa_g'].mean()), 1),
        }

    top_proteina = df.nlargest(7, 'proteina_g')[['nombre','proteina_g','categoria']]\
                     .to_dict('records')
    ig_conteo = df['indice_glucemico'].value_counts().to_dict()

    return {
        'por_categoria':   por_cat,
        'top_proteina':    top_proteina,
        'ig_distribucion': ig_conteo,
    }


def _calcular_kmeans():
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score

    df = ai_engine.df_ingredientes.copy()
    feats = ['calorias', 'proteina_g', 'carbohidratos_g', 'grasa_g', 'fibra_g',
             'azucar_g', 'grasa_saturada_g', 'sodio_mg']
    for f in feats:
        df[f] = pd.to_numeric(df[f], errors='coerce')
    df = df.dropna(subset=feats).reset_index(drop=True)
    X = StandardScaler().fit_transform(df[feats])

    inercias, siluetas = [], []
    for k in range(2, 11):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        lbl = km.fit_predict(X)
        inercias.append(round(float(km.inertia_), 1))
        siluetas.append(round(float(silhouette_score(X, lbl)), 3))

    km4 = KMeans(n_clusters=4, random_state=42, n_init=10)
    clusters = km4.fit_predict(X)
    pca = PCA(n_components=2, random_state=42)
    X2 = pca.fit_transform(X)
    centros2 = pca.transform(km4.cluster_centers_)
    var_exp = [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_]

    scatter = [
        {'x': round(float(X2[i, 0]), 3), 'y': round(float(X2[i, 1]), 3),
         'cluster': int(clusters[i]), 'nombre': df.iloc[i]['nombre'],
         'categoria': df.iloc[i]['categoria']}
        for i in range(len(df))
    ]
    centros = [
        {'x': round(float(centros2[c, 0]), 3), 'y': round(float(centros2[c, 1]), 3)}
        for c in range(4)
    ]

    return {
        'rango_k':   list(range(2, 11)),
        'inercias':  inercias,
        'siluetas':  siluetas,
        'k_usado':   4,
        'silueta_k4': siluetas[2],  # índice 2 → k=4
        'var_exp':   var_exp,
        'scatter':   scatter,
        'centros':   centros,
    }


def _calcular_vve():
    perfiles_prueba = [
        ('Hombre joven\nganar músculo',
         PerfilUsuario(edad=25, sexo='M', peso_kg=75, altura_cm=175,
                       nivel_actividad='moderado', objetivo='ganar_musculo')),
        ('Mujer adulta\nperder grasa',
         PerfilUsuario(edad=35, sexo='F', peso_kg=65, altura_cm=162,
                       nivel_actividad='sedentario', objetivo='perder_grasa')),
        ('Adulto mayor\nmantener peso',
         PerfilUsuario(edad=55, sexo='M', peso_kg=80, altura_cm=170,
                       nivel_actividad='ligero', objetivo='mantener')),
        ('Mujer activa\nganar músculo',
         PerfilUsuario(edad=22, sexo='F', peso_kg=58, altura_cm=165,
                       nivel_actividad='intenso', objetivo='ganar_musculo')),
    ]

    def desv(real, tgt):
        return round((real - tgt) / tgt * 100, 1) if tgt else 0

    resultados = []
    for label, perfil in perfiles_prueba:
        plan     = generar_plan_completo(perfil)
        t        = plan['targets_dia']
        td       = plan['totales_dia']
        factible = all(len(c['plan']) > 0 for c in plan['comidas'])

        resultados.append({
            'label':             label,
            'kcal_target':       t['calorias_objetivo'],
            'kcal_real':         td['kcal'],
            'desv_kcal':         desv(td['kcal'],       t['calorias_objetivo']),
            'desv_proteina':     desv(td['proteina'],   t['proteina_g']),
            'desv_carbos':       desv(td['carbos'],     t['carbos_g']),
            'desv_grasa':        desv(td['grasa'],      t['grasa_g']),
            'factible':          factible,
            'num_comidas':       len(plan['comidas']),
            'ing_unicos':        plan['ingredientes_unicos'],
        })
    return {'perfiles': resultados}


@app.get("/api/admin/stats")
def get_admin_stats():
    """Estadísticas del dataset (servido desde caché tras warm-up)."""
    global _cache_stats
    if _cache_stats is None:
        _cache_stats = _calcular_stats()
    return _cache_stats


@app.get("/api/admin/kmeans")
def get_kmeans_data():
    """K-Means (k=2..10) + PCA 2D (servido desde caché tras warm-up)."""
    global _cache_kmeans
    if _cache_kmeans is None:
        _cache_kmeans = _calcular_kmeans()
    return _cache_kmeans


@app.get("/api/admin/vve")
def get_vve_results():
    """Suite VV&E con 4 perfiles (servido desde caché tras warm-up)."""
    global _cache_vve
    if _cache_vve is None:
        _cache_vve = _calcular_vve()
    return _cache_vve


@app.get("/api/ingredientes")
def get_todos_ingredientes():
    """Retorna todos los ingredientes del dataset agrupados por categoría."""
    grupos: dict = {}
    for _, row in ai_engine.df_ingredientes.iterrows():
        cat = row['categoria']
        if cat not in grupos:
            grupos[cat] = []
        grupos[cat].append({'nombre': row['nombre'], 'categoria': cat})
    return grupos


@app.get("/api/usuario/{username}/ingredientes")
def get_ingredientes_usuario(username: str, db: Session = Depends(get_db)):
    """Ingredientes disponibles del usuario. null en DB = todos."""
    user = get_usuario_or_404(db, username)
    if user.ingredientes_json:
        return {"ingredientes": json.loads(user.ingredientes_json), "personalizado": True}
    return {"ingredientes": ai_engine.df_ingredientes['nombre'].tolist(), "personalizado": False}


@app.post("/api/usuario/{username}/ingredientes")
def guardar_ingredientes(username: str, req: IngredientesRequest,
                         db: Session = Depends(get_db)):
    """Guarda la selección y borra el plan de hoy para regenerarlo."""
    user = get_usuario_or_404(db, username)
    todos = set(ai_engine.df_ingredientes['nombre'].tolist())
    seleccion = [n for n in req.ingredientes if n in todos]
    if len(seleccion) == len(todos):
        user.ingredientes_json = None       # usa todos → no guardar lista
    else:
        user.ingredientes_json = json.dumps(seleccion, ensure_ascii=False)
    # Borrar plan de hoy para forzar regeneración con nuevos ingredientes
    plan_db = db.query(PlanDiario).filter(
        PlanDiario.usuario_id == user.id,
        PlanDiario.fecha == date.today()
    ).first()
    if plan_db:
        db.delete(plan_db)
    db.commit()
    return {"ok": True, "total_seleccionados": len(seleccion)}


@app.get("/api/usuario/{username}/plan")
def get_plan(username: str, db: Session = Depends(get_db)):
    """Devuelve el plan del día. Lo genera si no existe todavía."""
    user = get_usuario_or_404(db, username)
    if not user.tiene_perfil():
        raise HTTPException(400, "El usuario no tiene perfil configurado")

    hoy = date.today()

    # ¿Ya existe plan para hoy?
    plan_db = db.query(PlanDiario).filter(
        PlanDiario.usuario_id == user.id,
        PlanDiario.fecha == hoy
    ).first()

    if plan_db:
        return json.loads(plan_db.plan_json)

    # Generar plan nuevo con variedad entre días
    perfil            = usuario_a_perfil(user)
    ingredientes_ant  = ingredientes_ultimos_dias(db, user.id, dias=2)
    disponibles       = json.loads(user.ingredientes_json) if user.ingredientes_json else None
    plan              = generar_plan_completo(perfil, ingredientes_ant or None, disponibles)

    # Guardar en DB
    nuevo = PlanDiario(
        usuario_id=user.id,
        fecha=hoy,
        plan_json=json.dumps(plan, ensure_ascii=False)
    )
    db.add(nuevo)
    db.commit()
    return plan


@app.delete("/api/usuario/{username}/plan/hoy")
def regenerar_plan(username: str, db: Session = Depends(get_db)):
    """Elimina el plan de hoy para forzar regeneración (útil en desarrollo)."""
    user = get_usuario_or_404(db, username)
    plan_db = db.query(PlanDiario).filter(
        PlanDiario.usuario_id == user.id,
        PlanDiario.fecha == date.today()
    ).first()
    if plan_db:
        db.delete(plan_db)
        db.commit()
    return {"ok": True}
