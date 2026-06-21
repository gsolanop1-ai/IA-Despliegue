# Bitácora de Decisiones del Proyecto
## Sistema Inteligente de Recomendación Alimenticia

**Curso:** Inteligencia Artificial: Principios y Técnicas (ISIA-108)
**Universidad:** UPAO — Semestre 2026-10
**Última actualización:** 

## 1. Descripción del proyecto

Sistema inteligente de recomendación alimenticia personalizada que entrega al usuario un plan diario (desayuno, almuerzo, cena, snack) con ingredientes específicos y cantidades exactas, basándose en sus datos personales (edad, sexo, peso, altura, nivel de actividad, objetivo) y aplicando técnicas de inteligencia artificial.

El proyecto está enfocado en ingredientes peruanos (incluyendo tarwi, kiwicha, maca, olluco) y cuenta con una arquitectura modular.

---

## 2. Resumen de decisiones tomadas

### 2.1 Técnicas de IA elegidas

| Capa | Técnica |
|---|---|
| 1 | Cálculo nutricional (Mifflin-St Jeor) |
| 2 | Sistema Experto con reglas |
| 3 | K-Means clustering |
| 4 | Optimización con PuLP (programación lineal) |
| 5 | LLM (Gemini API) — Nombrado de platillos |

### 2.2 Decisiones técnicas específicas

| Componente | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| Fórmula calórica | Mifflin-St Jeor (1990) | Harris-Benedict (1919) | Mifflin-St Jeor es más precisa para población general |
| Tipo de reglas del Sistema Experto | Soft rules (con pesos) + Hard rules estructurales | Solo hard rules | Soft rules evitan que el sistema falle por restricciones contradictorias |
| Implementación del motor de reglas | A mano (clase Python) | Librería `experta` | Mayor control, mejor pedagógicamente |
| Algoritmo de optimización | Programación lineal con PuLP | Algoritmos genéticos, hill climbing | Más limpio, didáctico y matemáticamente óptimo |

---

## 3. Decisiones sobre el dataset

### 3.1 Origen de los datos

Se construyó un dataset propio de 81 ingredientes con valores verificados contra fuentes oficiales.

### 3.2 Estructura del dataset propio

- **81 ingredientes** distribuidos en 8 categorías
- **18 columnas** con macros, micronutrientes, índice glucémico
- **Estandarizado a 100g** todos los valores
- **Estado cocido** para todos los ingredientes consumidos cocidos
- **Validado contra:** USDA FoodData Central oficial y Tabla Peruana de Composición de Alimentos del Instituto Nacional de Salud (INS)

### 3.3 Distribución por categorías

| Categoría | Cantidad | Tipo de uso |
|---|---|---|
| Proteínas | 14 | Principal |
| Carbohidratos | 19 | Principal |
| Grasas | 7 | Principal |
| Lácteos | 4 | Principal |
| Bebidas | 3 | Principal |
| Frutas | 17 | Principal |
| Verduras | 12 | Principal |
| Condimentos | 5 | Condimento |

---

## 4. Catálogo de reglas del sistema

Ver `docs/catalogo_reglas.md` para el detalle completo de las 15 reglas activas.

### Resumen de grupos:

| Grupo | Tipo | Cantidad | Ubicación | Descripción |
|---|---|---|---|---|
| A | SOFT | 4 | Sistema Experto | Reglas de salud |
| B | SOFT | 3 | Sistema Experto | Contexto del momento |
| C | HARD | 4 | Optimizador | Estructura por comida |
| D | HARD | 3 | Celda 5 | Reparto de macros |
| E | HARD | 1 | Celda 5 | Seguridad calórica |

---

## 5. Estructura del notebook

El notebook se organiza en 11 celdas:

1. Setup del entorno
2. Carga del dataset
3. Análisis exploratorio (EDA)
4. Cálculo nutricional
5. Reparto de macros
6. Perfil del usuario
7. Sistema Experto
8. K-Means Clustering
9. Optimización con PuLP
10. Orquestador del Plan Diario
11. Ejecución del Sistema

---

## 6. Atributos del graduado cubiertos

El proyecto evidencia los siguientes atributos del perfil de egreso:

- **AG-C09 (Diseño y Desarrollo de Soluciones):** solución para problema complejo de recomendación alimenticia
- **AG-C11 (Uso de Herramientas):** aplicación de Python, PuLP, scikit-learn
- **AG-C12 (Teoría y Fundamentos):** aplicación de teoría de IA y fundamentos de software

---

## 7. Riesgos identificados y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| PuLP devuelve "infactible" | Alto | Sistema de soft rules + fallback automático |
| K-Means da resultados inestables | Bajo | 81 ingredientes suficientes; `random_state` fijo |

---

*Esta bitácora sirve como documento de referencia para el equipo y como evidencia de las decisiones técnicas que respaldan el proyecto.*
