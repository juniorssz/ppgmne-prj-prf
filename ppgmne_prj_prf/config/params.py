# Parâmetros dos acidentes:
UF = "PR"

STR_COLS_TO_LOWER = [
    "dia_semana",
    "causa_acidente",
    "tipo_acidente",
    "classificacao_acidente",
    "fase_dia",
    "sentido_via",
    "tipo_pista",
    "tracado_via",
    "uso_solo",
]
STR_COLS_TO_UPPER = ["municipio", "regional", "delegacia", "uop"]

COORDS_MIN_DECIMAL_PLACES = 3

COORDS_PRECISION = 2

N_CLUSTERS = 8
CLUSTERING_FEATS = ["point_acc"]

# Parâmetros do IBGE
IBGE_YEAR = 2019
