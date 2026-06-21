# Estado del Proyecto

**Última actualación:** 

## Avance: Versión 1.0 — Sistema completado

### Implementado y validado

- [x] Módulo de cálculo nutricional 
  - Mifflin-St Jeor para TMB
  - Factores de actividad para GET
  - Reparto de macros según objetivo
  - Distribución calórica entre 4 comidas
  - Regla de seguridad calórica

- [x] Módulo de perfil de usuario 
  - Validación robusta de inputs
  - Diseño modular para futuras fuentes

- [x] Sistema Experto 
  - Grupo A: Reglas de salud (4 reglas)
  - Grupo B: Reglas de contexto (3 reglas)

- [x] K-Means Clustering
  - 4 clusters nutricionales identificados
  - Visualización con PCA
  - Coeficiente de silueta: 0.45

- [x] Optimizador con PuLP 
  - Programación lineal mixta entera
  - Grupo C: Estructura por comida (4 reglas)
  - Grupo D: Reparto de macros (3 reglas)
  - Grupo E: Seguridad calórica (1 regla)
  - Fallback automático ante infactibilidad

- [x] Orquestador del Plan Diario
  - Memoria entre comidas (penalización ×0.3)
  - Generación coordinada de las 4 comidas

### Validación realizada

- 4 perfiles de prueba ejecutados con éxito
- Desviación calórica promedio: 1.7%
- 16 comidas generadas sin infactibilidades
- Casos cubiertos:
  - Hombre joven, ganar músculo
  - Mujer adulta, perder grasa
  - Adulto mayor, mantener peso (activa reglas A3/A4)
  - Mujer joven activa, ganar músculo

### Total de reglas activas: 15

| Grupo | Tipo | Cantidad | Ubicación |
|---|---|---|---|
| A | SOFT | 4 | Sistema Experto |
| B | SOFT | 3 | Sistema Experto |
| C | HARD | 4 | Optimizador |
| D | HARD | 3 | Celda 5 |
| E | HARD | 1 | Celda 5 |

## Estructura del repositorio

```
proyecto_ia/
├── README.md Descripción general
├── ESTADO.md Este archivo
├── requirements.txt Dependencias
├── .gitignore
│
├── data/
│ └── ingredientes_dataset.csv 81 ingredientes curados
│
├── docs/
│ ├── bitacora_decisiones.md
│ └── catalogo_reglas.md
│
└── notebooks/
└── demo.ipynb Versión Colab
```

### Para trabajar en Colab

1. Sube `data/ingredientes_dataset.csv` a tu Google Drive en `/MyDrive/proyecto_ia/`
2. Abre `notebooks/demo.ipynb` en Colab
3. Ejecuta todas las celdas en orden
