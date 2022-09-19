from pathlib import Path

from ppgmne_prj_prf.config.params import UF

# Caminhos na pasta raíz do projeto
PATH_ROOT = Path(__file__).parents[2].absolute()

PATH_PPGMNE_PRF = PATH_ROOT / "ppgmne_prj_prf"

# Caminhos em data/
PATH_DATA = PATH_ROOT / "data"

PATH_DATA_PRF = PATH_DATA / "prf"
PATH_DATA_PRF_CACHE = PATH_DATA_PRF / "cache"
PATH_DATA_PRF_CACHE_DATABASE = PATH_DATA_PRF_CACHE / "database"

PATH_DATA_IBGE = PATH_DATA / "ibge"
PATH_DATA_IBGE_UF = PATH_DATA_IBGE / UF
PATH_DATA_IBGE_BORDERS = PATH_DATA_IBGE / UF / "borders"
