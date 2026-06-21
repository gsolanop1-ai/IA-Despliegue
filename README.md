# NutriPerú — Sistema Inteligente de Recomendación Alimenticia

> Proyecto académico — Inteligencia Artificial: Principios y Técnicas (ISIA-108)  
> Universidad Privada Antenor Orrego · Semestre 2026-10

Sistema de recomendación nutricional personalizada que genera planes alimenticios diarios completos (desayuno, almuerzo, cena, snack) con ingredientes peruanos. Integra un **Sistema Experto basado en reglas**, **optimización lineal entera (MILP)**, **K-Means clustering** e **inteligencia artificial generativa (LLM)**.

---

## Demo en producción

**URL pública:** _(disponible tras deploy en Render.com)_  
**Panel académico:** `<url>/admin`

> Usuario de acceso al panel: `admin`

---

## Arquitectura del sistema

```
Usuario
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│  Capa 1 — Cálculo nutricional (Mifflin-St Jeor)         │
│           TMB → GET → targets calóricos + macros        │
├──────────────────────────────────────────────────────────┤
│  Capa 2 — Sistema Experto (15 reglas heurísticas)       │
│           Grupos A (salud) + B (contexto temporal)      │
├──────────────────────────────────────────────────────────┤
│  Capa 3 — K-Means Clustering (k=4, silueta=0.450)      │
│           Validación de coherencia nutricional           │
├──────────────────────────────────────────────────────────┤
│  Capa 4 — Optimizador MILP (PuLP)                       │
│           Minimiza desviación calórica/macros           │
├──────────────────────────────────────────────────────────┤
│  Capa 5 — LLM generativo (Gemini + fallback local)      │
│           Nombres creativos para cada platillo           │
└──────────────────────────────────────────────────────────┘
  │
  ▼
Plan diario personalizado (4 comidas · gramos exactos)
```

---

## Dataset

- **81 ingredientes** peruanos con 16 atributos nutricionales cada uno
- Validado contra USDA FoodData Central y Tabla Peruana (INS)
- Distribución: Carbohidratos (19) · Frutas (17) · Proteínas (14) · Verduras (12) · Grasas (7) · Condimentos (5) · Lácteos (4) · Bebidas (3)

---

## Sistema Experto — Base de Reglas (15 reglas)

| ID | Grupo | Descripción |
|----|-------|-------------|
| A1 | Salud | Penaliza ×0.5 ingredientes con grasa saturada >7g → objetivo `perder_grasa` |
| A2 | Salud | Incentiva ×1.5 proteínas ≥25g/100g → objetivo `ganar_musculo` |
| A3 | Salud | Penaliza ×0.5 grasa saturada >5g → edad >50 años |
| A4 | Salud | Incentiva ×1.5 grasas saludables (palta, nueces, chía, jurel...) → edad >50 |
| B1 | Contexto | Habilita carnes proteicas en desayuno → `ganar_musculo` |
| B2 | Contexto | Incentiva ×1.5 ingredientes etiquetados para snack |
| B3 | Contexto | Incentiva pescado/hojas verdes, penaliza carnes rojas en cena → `perder_grasa` |
| C1-C3 | Macros | Distribución P/C/G por objetivo: 40/35/25 · 30/45/25 · 35/40/25 |
| D1-D4 | Estructura | Ingredientes obligatorios por comida (ej. proteína+carbohidrato+verdura en almuerzo) |
| E1 | Seguridad | Mínimo calórico: 1500 kcal (H) / 1200 kcal (M) |

---

## Resultados de la Suite VV&E

| # | Perfil | Target (kcal) | Real (kcal) | Desv. Cal. |
|---|--------|:-------------:|:-----------:|:----------:|
| P1 | Hombre, 25a, 75kg, moderado, ganar músculo | 3073 | ~3052 | −0.7% |
| P2 | Mujer, 35a, 65kg, sedentaria, perder grasa | 1273 | ~1222 | −4.0% |
| P3 | Hombre, 55a, 80kg, ligero, mantener | 2190 | ~2194 | +0.2% |
| P4 | Mujer, 22a, 58kg, intensa, ganar músculo | 2659 | ~2610 | −1.8% |
| AVG | Promedio absoluto | — | — | **±1.7%** |

Desviacíon calórica promedio del **1.7%** — muy por debajo del umbral del 10% (RNF1).

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| Backend | FastAPI + Python 3.11 |
| Base de datos | SQLite (local) / PostgreSQL (producción) |
| ORM | SQLAlchemy |
| Optimización | PuLP (MILP) |
| Clustering | scikit-learn (KMeans, PCA, StandardScaler) |
| Frontend | HTML + CSS + JavaScript vanilla |
| LLM | Google Gemini + fallback local |
| Despliegue | Render.com |

---

## Estructura del proyecto

```
PROYECTO_IA/
├── data/
│   └── ingredientes_dataset.csv     # 81 ingredientes curados
├── docs/
│   ├── bitacora_decisiones.md       # Registro de decisiones técnicas
│   └── catalogo_reglas.md           # Catálogo formal de las 15 reglas
├── notebooks/
│   └── demo.ipynb                   # Notebook ejecutable en Google Colab
├── webapp/
│   ├── main.py                      # Endpoints FastAPI + panel académico
│   ├── ai_engine.py                 # Motor de IA (SE + MILP + Orquestador)
│   ├── models.py                    # Modelos SQLAlchemy (Usuario, PlanDiario)
│   ├── database.py                  # Conexión SQLite/PostgreSQL
│   ├── requirements.txt             # Dependencias de producción
│   └── static/                      # Frontend (HTML, CSS, JS)
│       ├── index.html               # Login
│       ├── perfil.html              # Formulario de perfil
│       ├── ingredientes.html        # Selección de ingredientes
│       ├── plan.html                # Plan del día + auditoría
│       └── admin.html               # Panel académico (stats, K-Means, VV&E)
├── requirements.txt                 # Dependencias del notebook
├── render.yaml                      # Configuración de despliegue
└── README.md
```

---

## Ejecución local

```bash
# 1. Clonar el repositorio
git clone https://github.com/gsolanop1-ai/PROYECTO_IA.git
cd PROYECTO_IA

# 2. Instalar dependencias
pip install -r webapp/requirements.txt

# 3. Ejecutar servidor
uvicorn webapp.main:app --reload --port 8001
```

Abrir en el navegador: `http://localhost:8001`

### Flujo de uso

1. Ingresar con un nombre de usuario en `/`
2. Completar el perfil nutricional en `/perfil`
3. Seleccionar ingredientes disponibles en `/ingredientes`
4. Ver el plan del día en `/plan` (incluye auditoría del Sistema Experto)
5. Acceder al panel académico con usuario `admin`

---

## Notebook en Google Colab

El notebook `notebooks/demo.ipynb` contiene el desarrollo completo del sistema:

| Celda | Contenido |
|-------|-----------|
| 1–3 | Carga y exploración del dataset (EDA) |
| 4–6 | Cálculo Mifflin-St Jeor y distribución de macros |
| 7 | Sistema Experto (reglas A1–A4, B1–B3) |
| 8 | K-Means clustering + análisis de silueta + PCA 2D |
| 9 | Optimizador PuLP (MILP) |
| 10 | Orquestador del plan diario |
| 11–13 | Integración LLM (Gemini + fallback) |
| 14 | Suite VV&E — verificación, validación y evaluación |

---

## Equipo

| Integrante | Código |
|------------|--------|
| Ángeles Pérez, Jhonny Luis | — |
| Castañeda Astudillo, André | — |
| Rodríguez Bocanegra, Cristian | — |
| Solano Pérez, Gabriel Alejandro | — |
| Villar Vigo, Robert Visitación Junior | — |

**Docente:** Hernán Sagastegui Chigne  
**Asignatura:** Inteligencia Artificial: Principios y Técnicas  
**Programa:** Ingeniería de Sistemas e Inteligencia Artificial — UPAO 2026-10
