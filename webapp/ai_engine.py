"""
Motor de IA — NutriPerú
=======================
Traslada la lógica del notebook demo.ipynb a un módulo Python
reutilizable desde el backend web (FastAPI).

Mapa notebook → módulo
----------------------
  Celdas 1-3   → carga de df_ingredientes (dataset 81 ingredientes)
  Celda  4     → calcular_tmb / calcular_get / calcular_targets_diarios
  Celda  5     → REGLAS_OBJETIVO, DISTRIBUCION_POR_OBJETIVO
  Celda  6     → clase PerfilUsuario
  Celda  7     → clase SistemaExperto  (reglas A1-A4, B1-B3 + estructura)
  Celda  9     → _construir_y_resolver / optimizar_comida  (PuLP MILP)
  Celda  10    → clase OrquestadorDiario
  Celdas 11-13 → generar_nombre_platillo (fallback local del LLM Gemini)

Nota: Celda 8 (K-Means + PCA) y Celda 14 (Suite VV&E) se ejecutan
      bajo demanda en los endpoints del panel académico (main.py).
"""

import os
import pandas as pd
from pulp import LpProblem, LpMinimize, LpVariable, LpStatus, lpSum, value, PULP_CBC_CMD

# ── [Celdas 1-3] Dataset — 81 ingredientes peruanos ──────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'ingredientes_dataset.csv')

df_ingredientes = pd.read_csv(DATASET_PATH, encoding='utf-8-sig')

# ── [Celdas 4-5] Constantes nutricionales ─────────────────────
FACTORES_ACTIVIDAD = {
    'sedentario': 1.20, 'ligero': 1.375, 'moderado': 1.55,
    'intenso': 1.725, 'muy_intenso': 1.90,
}

REGLAS_OBJETIVO = {
    'perder_grasa':  {'ajuste_calorico': 0.80, 'pct_proteina': 0.40, 'pct_carbos': 0.35, 'pct_grasa': 0.25},
    'mantener':      {'ajuste_calorico': 1.00, 'pct_proteina': 0.30, 'pct_carbos': 0.45, 'pct_grasa': 0.25},
    'ganar_musculo': {'ajuste_calorico': 1.15, 'pct_proteina': 0.35, 'pct_carbos': 0.40, 'pct_grasa': 0.25},
}

DISTRIBUCION_POR_OBJETIVO = {
    'perder_grasa':  {'desayuno': 0.25, 'almuerzo': 0.35, 'cena': 0.30, 'snack': 0.10},
    'mantener':      {'desayuno': 0.25, 'almuerzo': 0.30, 'cena': 0.30, 'snack': 0.15},
    'ganar_musculo': {'desayuno': 0.22, 'almuerzo': 0.33, 'cena': 0.30, 'snack': 0.15},
}

MINIMO_KCAL_SEGURIDAD = {'M': 1500, 'F': 1200}

# ── [Celda 4] Fórmula Mifflin-St Jeor ────────────────────────
def calcular_tmb(peso_kg, altura_cm, edad, sexo):
    if sexo.upper() == 'M':
        return 10 * peso_kg + 6.25 * altura_cm - 5 * edad + 5
    return 10 * peso_kg + 6.25 * altura_cm - 5 * edad - 161

def calcular_get(tmb, nivel_actividad):
    return tmb * FACTORES_ACTIVIDAD[nivel_actividad]

def calcular_targets_diarios(get, objetivo, sexo='M'):
    regla    = REGLAS_OBJETIVO[objetivo]
    cal_calc = get * regla['ajuste_calorico']
    minimo   = MINIMO_KCAL_SEGURIDAD.get(sexo.upper(), 1200)
    cal_final = max(cal_calc, minimo)
    return {
        'calorias_objetivo': round(cal_final),
        'proteina_g': round(cal_final * regla['pct_proteina'] / 4),
        'carbos_g':   round(cal_final * regla['pct_carbos']   / 4),
        'grasa_g':    round(cal_final * regla['pct_grasa']    / 9),
        'objetivo':   objetivo,
    }

def repartir_por_comida(targets):
    dist = DISTRIBUCION_POR_OBJETIVO[targets['objetivo']]
    return {
        c: {
            'calorias_objetivo': round(targets['calorias_objetivo'] * f),
            'proteina_g':        round(targets['proteina_g'] * f),
            'carbos_g':          round(targets['carbos_g'] * f),
            'grasa_g':           round(targets['grasa_g'] * f),
        } for c, f in dist.items()
    }

# ── [Celda 6] Perfil de usuario ───────────────────────────────
class PerfilUsuario:
    OPCIONES_VALIDAS = {
        'sexo':            ['M', 'F'],
        'nivel_actividad': list(FACTORES_ACTIVIDAD.keys()),
        'objetivo':        list(REGLAS_OBJETIVO.keys()),
    }

    def __init__(self, edad, sexo, peso_kg, altura_cm, nivel_actividad, objetivo):
        if not (10 <= edad <= 100):       raise ValueError(f'Edad fuera de rango: {edad}')
        if not (30 <= peso_kg <= 250):    raise ValueError(f'Peso fuera de rango: {peso_kg}')
        if not (100 <= altura_cm <= 230): raise ValueError(f'Altura fuera de rango: {altura_cm}')

        valores = {'sexo': sexo, 'nivel_actividad': nivel_actividad, 'objetivo': objetivo}
        for campo, opciones in self.OPCIONES_VALIDAS.items():
            if valores[campo] not in opciones:
                raise ValueError(f"'{campo}' inválido: {valores[campo]}")

        self.edad            = edad
        self.sexo            = sexo.upper()
        self.peso_kg         = peso_kg
        self.altura_cm       = altura_cm
        self.nivel_actividad = nivel_actividad
        self.objetivo        = objetivo

    def calcular_targets(self):
        tmb = calcular_tmb(self.peso_kg, self.altura_cm, self.edad, self.sexo)
        get = calcular_get(tmb, self.nivel_actividad)
        t   = calcular_targets_diarios(get, self.objetivo, sexo=self.sexo)
        t['tmb'], t['get'] = round(tmb), round(get)
        return t

# ── [Celda 7] Sistema Experto — 15 reglas heurísticas ─────────
class SistemaExperto:
    ESTRUCTURA_POR_COMIDA = {
        'desayuno': {'obligatorios': ['Carbohidrato']},
        'almuerzo': {'obligatorios': ['Proteina', 'Carbohidrato', 'Verdura']},
        'cena':     {'obligatorios': ['Proteina', 'Verdura']},
        'snack':    {'obligatorios': []},
    }
    INGREDIENTES_SALUDABLES_MAYORES = [
        'Palta', 'Nueces', 'Chia', 'Salmon', 'Jurel', 'Caballa', 'Almendras'
    ]

    def __init__(self, df):
        self.df_original      = df.copy()
        self.reglas_aplicadas = []

    def _aplicar_reglas_salud(self, df, perfil):
        if perfil.objetivo == 'perder_grasa':
            mask = df['grasa_saturada_g'] > 7
            df.loc[mask, 'peso'] *= 0.5
            if mask.any():
                self.reglas_aplicadas.append(f'A1: peso×0.5 a {mask.sum()} ing. grasa sat. >7g')
        if perfil.objetivo == 'ganar_musculo':
            mask = (df['categoria'] == 'Proteina') & (df['proteina_g'] >= 25)
            df.loc[mask, 'peso'] *= 1.5
            if mask.any():
                self.reglas_aplicadas.append(f'A2: peso×1.5 a {mask.sum()} proteínas ≥25g')
        if perfil.edad > 50:
            mask_a3 = df['grasa_saturada_g'] > 5
            df.loc[mask_a3, 'peso'] *= 0.5
            if mask_a3.any():
                self.reglas_aplicadas.append(f'A3: peso×0.5 a {mask_a3.sum()} ing. (edad>50)')
            mask_a4 = df['nombre'].isin(self.INGREDIENTES_SALUDABLES_MAYORES)
            df.loc[mask_a4, 'peso'] *= 1.5
            if mask_a4.any():
                self.reglas_aplicadas.append(f'A4: peso×1.5 a {mask_a4.sum()} grasas saludables')
        return df

    def _aplicar_reglas_contexto(self, df, perfil, comida):
        if comida == 'desayuno' and perfil.objetivo == 'ganar_musculo':
            self.reglas_aplicadas.append('B1: carnes habilitadas en desayuno')
        if comida == 'snack':
            mask = df['comidas_recomendadas'].str.contains('snack', na=False)
            df.loc[mask, 'peso'] *= 1.5
            if mask.any():
                self.reglas_aplicadas.append(f'B2: peso×1.5 a {mask.sum()} ing. snack')
        if comida == 'cena' and perfil.objetivo == 'perder_grasa':
            mask_p = df['grupo_intercambiable'].isin(['pescado_magro', 'hoja_verde'])
            df.loc[mask_p, 'peso'] *= 1.5
            mask_d = df['grupo_intercambiable'] == 'carne_roja'
            df.loc[mask_d, 'peso'] *= 0.7
            self.reglas_aplicadas.append('B3: cena light → +pescado/hojas, -carnes')
        return df

    def _filtrar_por_momento(self, df, comida):
        if comida is None:
            return df
        return df[df['comidas_recomendadas'].str.contains(comida, na=False)]

    def evaluar(self, perfil, comida):
        self.reglas_aplicadas = []
        df = self.df_original.copy()
        df['peso'] = 1.0
        df_condimentos = df[df['tipo_uso'] == 'condimento'].copy()
        df = df[df['tipo_uso'] == 'principal'].copy()
        df = self._filtrar_por_momento(df, comida)
        df = self._aplicar_reglas_salud(df, perfil)
        df = self._aplicar_reglas_contexto(df, perfil, comida)
        targets_diarios = perfil.calcular_targets()
        targets_comida  = repartir_por_comida(targets_diarios)[comida]
        return {
            'ingredientes_principales': df.reset_index(drop=True),
            'condimentos':              df_condimentos.reset_index(drop=True),
            'estructura':               self.ESTRUCTURA_POR_COMIDA.get(comida, {'obligatorios': []}),
            'targets':                  targets_comida,
            'reglas_log':               self.reglas_aplicadas.copy(),
            'comida':                   comida,
        }

# ── [Celda 9] Optimizador PuLP — MILP ────────────────────────
PORCIONES_BASE = {
    'Proteina':     {'min': 80,  'max': 250},
    'Carbohidrato': {'min': 30,  'max': 220},
    'Verdura':      {'min': 50,  'max': 150},
    'Grasa':        {'min': 15,  'max': 60},
    'Lacteo':       {'min': 30,  'max': 300},
    'Bebida':       {'min': 100, 'max': 400},
    'Fruta':        {'min': 50,  'max': 250},
}
MAX_POR_CATEGORIA_BASE = {
    'Proteina': 1, 'Carbohidrato': 1, 'Grasa': 1,
    'Lacteo': 1, 'Bebida': 1, 'Fruta': 1, 'Verdura': 2,
}
PORCIONES_SNACK = {
    'perder_grasa':  {'Fruta': {'min': 80,'max': 200}, 'Lacteo': {'min': 80,'max': 150}, 'Verdura': {'min': 50,'max': 100}, 'Grasa': {'min': 10,'max': 20}},
    'mantener':      {'Fruta': {'min': 80,'max': 200}, 'Lacteo': {'min': 80,'max': 200}, 'Grasa': {'min': 15,'max': 30}, 'Proteina': {'min': 30,'max': 100}},
    'ganar_musculo': {'Proteina': {'min': 30,'max': 150}, 'Lacteo': {'min': 50,'max': 150}, 'Fruta': {'min': 80,'max': 200}, 'Carbohidrato': {'min': 30,'max': 80}, 'Grasa': {'min': 20,'max': 50}},
}
MAX_POR_CATEGORIA_SNACK = {
    'perder_grasa':  {'Fruta': 1, 'Lacteo': 1, 'Verdura': 1, 'Grasa': 1},
    'mantener':      {'Fruta': 1, 'Lacteo': 1, 'Grasa': 1, 'Proteina': 1},
    'ganar_musculo': {'Proteina': 1, 'Lacteo': 1, 'Fruta': 1, 'Carbohidrato': 1, 'Grasa': 1},
}
CATEGORIAS_SNACK = {
    'perder_grasa':  ['Fruta', 'Lacteo', 'Verdura', 'Grasa'],
    'mantener':      ['Fruta', 'Lacteo', 'Grasa', 'Proteina'],
    'ganar_musculo': ['Proteina', 'Lacteo', 'Fruta', 'Carbohidrato', 'Grasa'],
}
CATEGORIAS_DESAYUNO   = ['Carbohidrato', 'Proteina', 'Lacteo', 'Grasa', 'Fruta', 'Bebida']
GRUPOS_PROTEINA_RAPIDA = ['huevo', 'yogurt', 'suplemento', 'queso']
LIMITE_INGREDIENTES    = {
    'perder_grasa':  {'desayuno': 3, 'almuerzo': 4, 'cena': 3, 'snack': 2},
    'mantener':      {'desayuno': 3, 'almuerzo': 4, 'cena': 3, 'snack': 2},
    'ganar_musculo': {'desayuno': 4, 'almuerzo': 5, 'cena': 4, 'snack': 4},
}
TOLERANCIA_CALORIAS = 0.10
TOLERANCIA_MACROS   = 0.25
LAMBDA_BONUS        = 1.0
PCT_PROTEINA_FORZADA = 0.70
MAX_INTENTOS_FALLBACK = 2
INCREMENTO_FALLBACK   = 1


def _construir_y_resolver(df, estructura, targets, es_snack,
                           porciones_config, max_cat_config, max_ingredientes):
    prob = LpProblem('Plan_Comida', LpMinimize)
    x, b = {}, {}
    for _, row in df.iterrows():
        idx = row['id']
        cat = row['categoria']
        cfg = porciones_config.get(cat, {'min': 20, 'max': 200})
        x[idx] = LpVariable(f'x_{idx}', lowBound=0, upBound=cfg['max'])
        b[idx] = LpVariable(f'b_{idx}', cat='Binary')
        prob += x[idx] >= cfg['min'] * b[idx]
        prob += x[idx] <= cfg['max'] * b[idx]

    def total(col):
        return lpSum((row[col] / 100) * x[row['id']] for _, row in df.iterrows())

    tk, tp = targets['calorias_objetivo'], targets['proteina_g']
    tc, tg = targets['carbos_g'], targets['grasa_g']
    total_kcal = total('calorias')
    total_p    = total('proteina_g')
    total_c    = total('carbohidratos_g')
    total_g_   = total('grasa_g')

    prob += total_kcal >= tk * (1 - TOLERANCIA_CALORIAS)
    prob += total_kcal <= tk * (1 + TOLERANCIA_CALORIAS)
    prob += total_p >= tp * (1 - TOLERANCIA_MACROS)
    prob += total_p <= tp * (1 + TOLERANCIA_MACROS)
    prob += total_c >= tc * (1 - TOLERANCIA_MACROS)
    prob += total_c <= tc * (1 + TOLERANCIA_MACROS)
    prob += total_g_ >= tg * (1 - TOLERANCIA_MACROS)
    prob += total_g_ <= tg * (1 + TOLERANCIA_MACROS)

    if not es_snack:
        prot_ppal = lpSum(
            (row['proteina_g'] / 100) * x[row['id']]
            for _, row in df.iterrows()
            if row['categoria'] in ('Proteina', 'Lacteo')
        )
        prob += prot_ppal >= tp * PCT_PROTEINA_FORZADA
        for cat_oblig in estructura.get('obligatorios', []):
            ids_cat = df[df['categoria'] == cat_oblig]['id'].tolist()
            if ids_cat:
                prob += lpSum(b[i] for i in ids_cat) >= 1

    for categoria in df['categoria'].unique():
        ids_cat  = df[df['categoria'] == categoria]['id'].tolist()
        max_perm = max_cat_config.get(categoria, 1)
        if len(ids_cat) > max_perm:
            prob += lpSum(b[i] for i in ids_cat) <= max_perm

    for grupo in df['grupo_intercambiable'].dropna().unique():
        ids_grupo = df[df['grupo_intercambiable'] == grupo]['id'].tolist()
        if len(ids_grupo) > 1:
            prob += lpSum(b[i] for i in ids_grupo) <= 1

    ids_bl = df[df['categoria'].isin(['Bebida', 'Lacteo'])]['id'].tolist()
    if len(ids_bl) > 1:
        prob += lpSum(b[i] for i in ids_bl) <= 1

    todos_ids = df['id'].tolist()
    if len(todos_ids) > max_ingredientes:
        prob += lpSum(b[i] for i in todos_ids) <= max_ingredientes

    dev_p = LpVariable('dev_prot',  lowBound=0)
    dev_c = LpVariable('dev_carb',  lowBound=0)
    dev_g = LpVariable('dev_grasa', lowBound=0)
    prob += dev_p >= total_p - tp;    prob += dev_p >= -(total_p - tp)
    prob += dev_c >= total_c - tc;    prob += dev_c >= -(total_c - tc)
    prob += dev_g >= total_g_ - tg;   prob += dev_g >= -(total_g_ - tg)
    bonus = lpSum(row['peso'] * x[row['id']] / 100 for _, row in df.iterrows())
    prob += dev_p + dev_c + dev_g - LAMBDA_BONUS * bonus
    prob.solve(PULP_CBC_CMD(msg=0))
    return LpStatus[prob.status], x, b


def optimizar_comida(resultado_experto, objetivo_usuario='mantener'):
    df_original = resultado_experto['ingredientes_principales']
    estructura  = resultado_experto['estructura']
    targets     = resultado_experto['targets']
    comida      = resultado_experto.get('comida', 'almuerzo')

    if len(df_original) == 0:
        return {'estado': 'infactible', 'mensaje': 'Sin ingredientes'}

    es_snack    = (comida == 'snack')
    es_desayuno = (comida == 'desayuno')

    if es_snack:
        porciones_config = PORCIONES_SNACK.get(objetivo_usuario, PORCIONES_SNACK['mantener'])
        max_cat_config   = MAX_POR_CATEGORIA_SNACK.get(objetivo_usuario, {})
        cats_perm        = CATEGORIAS_SNACK.get(objetivo_usuario, ['Fruta', 'Lacteo'])
        df = df_original[df_original['categoria'].isin(cats_perm)].copy()
        df = df[~df['grupo_intercambiable'].isin(['legumbre_proteica', 'legumbre', 'grano_andino', 'tuberculo'])]
        if objetivo_usuario == 'ganar_musculo':
            mask = df['grupo_intercambiable'].isin(GRUPOS_PROTEINA_RAPIDA)
            df.loc[mask, 'peso'] *= 1.5
    elif es_desayuno:
        porciones_config = PORCIONES_BASE
        max_cat_config   = MAX_POR_CATEGORIA_BASE
        df = df_original[df_original['categoria'].isin(CATEGORIAS_DESAYUNO)].copy()
        df = df[(df['grupo_intercambiable'] != 'tuberculo') | (df['nombre'] == 'Camote')]
    else:
        porciones_config = PORCIONES_BASE
        max_cat_config   = MAX_POR_CATEGORIA_BASE
        df = df_original.copy()

    if len(df) == 0:
        return {'estado': 'infactible', 'mensaje': f'Sin ingredientes para {comida}'}

    limite_inicial = LIMITE_INGREDIENTES.get(objetivo_usuario, {}).get(comida, 4)
    estado_final, x_final, intento_final, fallback = None, None, 0, False

    for intento in range(MAX_INTENTOS_FALLBACK + 1):
        max_ing = limite_inicial + intento * INCREMENTO_FALLBACK
        estado, x, b = _construir_y_resolver(
            df, estructura, targets, es_snack,
            porciones_config, max_cat_config, max_ing
        )
        if estado == 'Optimal':
            estado_final, x_final, intento_final = estado, x, intento
            fallback = (intento > 0)
            break

    if estado_final != 'Optimal':
        return {'estado': 'infactible', 'targets': targets}

    plan = []
    for _, row in df.iterrows():
        gramos = value(x_final[row['id']])
        if gramos and gramos > 0.5:
            plan.append({
                'nombre':   row['nombre'],
                'categoria': row['categoria'],
                'gramos':   round(gramos),
                'kcal':     round((row['calorias']        / 100) * gramos),
                'proteina': round((row['proteina_g']      / 100) * gramos, 1),
                'carbos':   round((row['carbohidratos_g'] / 100) * gramos, 1),
                'grasa':    round((row['grasa_g']         / 100) * gramos, 1),
            })

    totales = {k: round(sum(p[k] for p in plan), 1 if k != 'kcal' else 0)
               for k in ['kcal', 'proteina', 'carbos', 'grasa']}
    totales['kcal'] = int(totales['kcal'])

    keys_map = {'kcal': 'calorias_objetivo', 'proteina': 'proteina_g',
                'carbos': 'carbos_g', 'grasa': 'grasa_g'}
    desv = {k: round((totales[k] - targets[keys_map[k]]) / targets[keys_map[k]] * 100, 1)
            for k in keys_map}

    return {
        'estado': 'optimo', 'plan': plan, 'totales': totales,
        'targets': targets, 'desviaciones': desv, 'comida': comida,
        'fallback_aplicado': fallback,
        'reglas_log': resultado_experto.get('reglas_log', []),
    }

# ── [Celda 10] Orquestador del plan diario ────────────────────
class OrquestadorDiario:
    def __init__(self, sistema_experto):
        self.sistema              = sistema_experto
        self.memoria_ingredientes = {}
        self.factor_penalizacion  = 0.3

    def _penalizar_usados(self, df_comida, comida_actual):
        if comida_actual == 'desayuno':
            return df_comida
        usados = set()
        for comida, nombres in self.memoria_ingredientes.items():
            if comida != comida_actual:
                usados.update(nombres)
        df_comida = df_comida.copy()
        mask = df_comida['nombre'].isin(usados)
        df_comida.loc[mask, 'peso'] *= self.factor_penalizacion
        return df_comida

    def generar_plan_diario(self, perfil, ingredientes_previos=None):
        """Genera las 4 comidas. ingredientes_previos evita repetición entre días."""
        self.memoria_ingredientes = {}
        if ingredientes_previos:
            # Pre-seed con ingredientes de días anteriores (no aplica a snack)
            self.memoria_ingredientes['_historial'] = list(ingredientes_previos)

        resultados = []
        for comida in ['desayuno', 'almuerzo', 'cena', 'snack']:
            res_exp = self.sistema.evaluar(perfil, comida)
            # Penalizar solo comidas principales (no snack)
            if comida != 'snack':
                res_exp['ingredientes_principales'] = self._penalizar_usados(
                    res_exp['ingredientes_principales'], comida
                )
            opt = optimizar_comida(res_exp, perfil.objetivo)
            if opt['estado'] == 'optimo':
                self.memoria_ingredientes[comida] = [p['nombre'] for p in opt['plan']]
                resultados.append(opt)

        return self._consolidar(resultados, perfil)

    def _consolidar(self, resultados, perfil):
        targets_dia = perfil.calcular_targets()
        totales_dia = {k: round(sum(r['totales'][k] for r in resultados), 1)
                       for k in ['kcal', 'proteina', 'carbos', 'grasa']}
        totales_dia['kcal'] = int(totales_dia['kcal'])
        keys_map = {'kcal': 'calorias_objetivo', 'proteina': 'proteina_g',
                    'carbos': 'carbos_g', 'grasa': 'grasa_g'}
        desv_dia = {k: round((totales_dia[k] - targets_dia[keys_map[k]])
                             / targets_dia[keys_map[k]] * 100, 1) for k in keys_map}
        unicos = set(p['nombre'] for r in resultados for p in r['plan'])
        return {
            'comidas':           resultados,
            'totales_dia':       totales_dia,
            'desviaciones_dia':  desv_dia,
            'targets_dia':       targets_dia,
            'ingredientes_unicos': len(unicos),
            'reglas_por_comida': {r['comida']: r.get('reglas_log', []) for r in resultados},
        }

# ── [Celdas 11-13] Generador de nombres — Gemini + fallback local
# Inicialización perezosa del cliente Gemini. Si la API key no está disponible
# o la librería no está instalada, se usa el generador local (idéntico al
# fallback del notebook).
_GEMINI_MODEL = None
_GEMINI_DISPONIBLE = False
try:
    _GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if _GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_API_KEY)
        _GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
        _GEMINI_DISPONIBLE = True
except Exception:
    _GEMINI_DISPONIBLE = False


_PLANTILLAS = {
    'desayuno': ['{prot} con {carbo} andino', 'Bowl de {prot} y {carbo}',
                 '{prot} nutritivo con {vegetal}', 'Desayuno fitness de {prot}'],
    'almuerzo': ['{prot} a la criolla con {carbo}', 'Segundo de {prot} con {vegetal}',
                 '{prot} guisado con {carbo}', 'Almuerzo peruano de {prot}'],
    'cena':     ['{prot} ligero con {vegetal}', 'Cena saludable de {prot}',
                 '{prot} al vapor con {vegetal}', 'Plato light de {prot} y {vegetal}'],
    'snack':    ['Snack proteico de {prot}', '{prot} con {fruta}',
                 'Colación de {prot} y {fruta}', 'Mini bowl de {prot}'],
}
_DESCRIPCIONES = [
    'Combinación nutritiva con ingredientes peruanos de alto valor proteico.',
    'Plato balanceado con proteínas, carbohidratos y vitaminas esenciales.',
    'Receta saludable inspirada en la gastronomía peruana tradicional.',
    'Opción nutritiva con ingredientes frescos del mercado peruano.',
]

def _generar_nombre_local(ingredientes_plan, tipo_comida):
    """Fallback determinístico cuando Gemini no está disponible."""
    cats    = {i['categoria'].lower(): i['nombre'] for i in ingredientes_plan}
    prot    = cats.get('proteina',    ingredientes_plan[0]['nombre'])
    carbo   = cats.get('carbohidrato', 'quinua')
    vegetal = cats.get('verdura',      'espinaca')
    fruta   = cats.get('fruta',        'plátano')
    tipo    = tipo_comida.lower() if tipo_comida.lower() in _PLANTILLAS else 'almuerzo'
    plantilla = _PLANTILLAS[tipo][hash(prot + tipo) % len(_PLANTILLAS[tipo])]
    nombre    = plantilla.format(prot=prot, carbo=carbo, vegetal=vegetal, fruta=fruta)
    desc      = _DESCRIPCIONES[hash(tipo + prot) % len(_DESCRIPCIONES)]
    return nombre.capitalize(), desc


def _generar_nombre_gemini(ingredientes_plan, tipo_comida):
    """Llama a Gemini para generar un nombre creativo y descripción breve.
    Devuelve (nombre, descripcion) o lanza excepción si falla."""
    lista = ", ".join(f"{i['nombre']} ({i['gramos']}g)" for i in ingredientes_plan)
    prompt = (
        f"Eres un chef peruano. Genera UN nombre creativo (máx 6 palabras) y "
        f"UNA descripción breve (máx 20 palabras) para un platillo de "
        f"{tipo_comida} con estos ingredientes: {lista}.\n"
        f"Responde EXACTAMENTE en este formato, sin texto extra:\n"
        f"NOMBRE: <nombre>\n"
        f"DESC: <descripción>"
    )
    resp = _GEMINI_MODEL.generate_content(
        prompt,
        generation_config={'temperature': 0.7, 'max_output_tokens': 80},
    )
    texto = (resp.text or "").strip()
    nombre, desc = None, None
    for linea in texto.splitlines():
        if linea.upper().startswith('NOMBRE:'):
            nombre = linea.split(':', 1)[1].strip()
        elif linea.upper().startswith('DESC:'):
            desc = linea.split(':', 1)[1].strip()
    if not nombre or not desc:
        raise ValueError(f"Respuesta Gemini con formato inválido: {texto[:120]}")
    return nombre, desc


def generar_nombre_platillo(ingredientes_plan, tipo_comida):
    """Genera nombre + descripción. Usa Gemini si está disponible; si no, fallback local."""
    if not ingredientes_plan:
        return "Platillo sin ingredientes", "Sin datos disponibles."
    if _GEMINI_DISPONIBLE:
        try:
            return _generar_nombre_gemini(ingredientes_plan, tipo_comida)
        except Exception:
            pass  # caer a fallback local en cualquier error de API
    return _generar_nombre_local(ingredientes_plan, tipo_comida)

# ── Orquestador público ───────────────────────────────────────
def generar_plan_completo(perfil: PerfilUsuario, ingredientes_previos=None,
                          ingredientes_disponibles=None) -> dict:
    """
    Genera un plan diario completo con nombres de platillos.
    ingredientes_previos:   set de nombres a evitar (de días anteriores).
    ingredientes_disponibles: list/set de nombres permitidos (None = todos).
    """
    df = df_ingredientes.copy()
    if ingredientes_disponibles:
        df_filtrado = df[df['nombre'].isin(ingredientes_disponibles)]
        if len(df_filtrado) >= 8:
            df = df_filtrado

    sistema      = SistemaExperto(df)
    orquestador  = OrquestadorDiario(sistema)
    plan         = orquestador.generar_plan_diario(perfil, ingredientes_previos)

    nombres_platillos = {}
    for comida_res in plan['comidas']:
        tipo = comida_res['comida']
        nombre, desc = generar_nombre_platillo(comida_res['plan'], tipo)
        nombres_platillos[tipo] = {'nombre': nombre, 'descripcion': desc}

    plan['nombres_platillos'] = nombres_platillos
    return plan
