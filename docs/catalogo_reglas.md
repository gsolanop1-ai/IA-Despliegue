# Catálogo de Reglas del Sistema

El sistema completo cuenta con **15 reglas activas** distribuidas en 5 grupos funcionales.

## Distribución general

| Grupo | Tipo | Cantidad | Ubicación | Descripción |
|---|---|---|---|---|
| A | SOFT | 4 | Sistema Experto (Celda 7) | Reglas de salud (modifican pesos) |
| B | SOFT | 3 | Sistema Experto (Celda 7) | Contexto del momento |
| C | HARD | 4 | Optimizador PuLP (Capa 4) | Estructura obligatoria por comida |
| D | HARD | 3 | Celda 5 | Reparto de macros según objetivo |
| E | HARD | 1 | Celda 5 | Seguridad calórica |
| **Total activas** | | **15** | | |

---

## Grupo A — Reglas de salud (SOFT, modifican pesos) - Ubicación: Celda 7

| ID | Condición | Acción |
|---|---|---|
| A1 | objetivo = perder_grasa | Peso × 0.5 a ingredientes con grasa saturada > 7g |
| A2 | objetivo = ganar_musculo Y categoria = Proteina | Peso × 1.5 a proteínas con ≥25g/100g |
| A3 | edad > 50 | Peso × 0.5 a ingredientes con grasa saturada > 5g |
| A4 | edad > 50 | Peso × 1.5 a palta, nueces, chía, salmón, jurel, caballa, almendras |

## Grupo B — Contexto del momento (SOFT) - Ubicación: Celda 7

| ID | Condición | Acción |
|---|---|---|
| B1 | desayuno + ganar_musculo | Habilitar carnes en desayuno |
| B2 | comida = snack | Peso × 1.5 a ingredientes con "snack" en comidas_recomendadas |
| B3 | cena + perder_grasa | Peso × 1.5 a pescado magro y hojas verdes; × 0.7 a carnes rojas |

## Grupo C — Estructura por comida (HARD) - Ubicación: Optimizador PuLP

| ID | Comida | Estructura obligatoria |
|---|---|---|
| C1 | desayuno | Mínimo 1 carbohidrato |
| C2 | almuerzo | Mínimo 1 proteína + 1 carbohidrato + 1 verdura |
| C3 | cena | Mínimo 1 proteína + 1 verdura |
| C4 | snack | Sin estructura rígida (configuración contextual por objetivo) |

## Grupo D — Reparto de macros según objetivo (HARD) - Ubicación: Celda 5

| ID | Objetivo | Ajuste calórico | Proteína | Carbos | Grasa |
|---|---|---|---|---|---|
| D1 | perder_grasa | GET × 0.80 | 40% | 35% | 25% |
| D2 | mantener | GET × 1.00 | 30% | 45% | 25% |
| D3 | ganar_musculo | GET × 1.15 | 35% | 40% | 25% |

## Grupo E — Seguridad calórica (HARD) - Ubicación: Celda 5

| ID | Condición | Acción |
|---|---|---|
| E1 | calorías_calculadas < mínimo_seguridad | Forzar calorías al mínimo (1500 hombre / 1200 mujer) y emitir advertencia |

## Cómo se evidencian en el log

Cada vez que el Sistema Experto evalúa un perfil, registra qué reglas de los **Grupos A y B** se dispararon:

```python
resultado = sistema.evaluar(perfil, 'almuerzo')
for regla in resultado['reglas_log']:
    print(regla)

# Ejemplo de salida:
# A2: peso×1.5 a 9 proteínas con ≥25g/100g
# B1: carnes habilitadas en desayuno (ganar músculo)  

