import json

import holidays
import numpy as np
import pandas as pd
import scipy.stats as stats
from loguru import logger
from pandera import Column, DataFrameSchema
from pandera.errors import SchemaError
from shapely.geometry import Point, Polygon

from ppgmne_prj_prf.config.params import (
    COORDS_MIN_DECIMAL_PLACES,
    STR_COLS_TO_LOWER,
    STR_COLS_TO_UPPER,
    UF,
)
from ppgmne_prj_prf.config.paths import (
    PATH_DATA_CACHE_MODEL,
    PATH_DATA_IBGE_BORDERS,
    PATH_DATA_PRF,
)
from ppgmne_prj_prf.utils import (
    clean_string,
    csv_zip_to_df,
    get_decimal_places,
    trace_df,
)


class Accidents:
    def __init__(self, verbose: bool = True) -> None:
        self.name = "accidents"
        self.uf = UF
        self.df = pd.DataFrame()
        self.verbose = verbose

        self.key_in = "id"

        self.df_schema_in: dict[str, Column] = {
            "id": Column(int),
            "ano": Column(int),
            "data_inversa": Column(str),
            "dia_semana": Column(str),
            "horario": Column(str),
            "uf": Column(str),
            "municipio": Column(str),
            "causa_acidente": Column(str),
            "tipo_acidente": Column(str, nullable=True),
            "classificacao_acidente": Column(str),
            "fase_dia": Column(str),
            "sentido_via": Column(str),
            "tipo_pista": Column(str),
            "tracado_via": Column(str),
            "uso_solo": Column(str),
            "pessoas": Column(int),
            "mortos": Column(int),
            "feridos_leves": Column(int),
            "feridos_graves": Column(int),
            "ilesos": Column(int),
            "ignorados": Column(int),
            "feridos": Column(int),
            "veiculos": Column(int),
            "latitude": Column(str),
            "longitude": Column(str),
            "regional": Column(str, nullable=True),
            "delegacia": Column(str, nullable=True),
            "uop": Column(str, nullable=True),
        }

        self.key_out = "id"

        self.df_schema_out: dict[str, Column] = {
            "id": Column(int),
            "ano": Column(int),
            "data_hora": Column("datetime64[ns]"),
            "dia_semana": Column(str),
            "uf": Column(str),
            "municipio": Column(str),
            "causa_acidente": Column(str),
            "tipo_acidente": Column(str),
            "classificacao_acidente": Column(str),
            "fase_dia": Column(str),
            "sentido_via": Column(str),
            "tipo_pista": Column(str),
            "tracado_via": Column(str),
            "uso_solo": Column(str),
            "pessoas": Column(int),
            "mortos": Column(int),
            "feridos_leves": Column(int),
            "feridos_graves": Column(int),
            "ilesos": Column(int),
            "ignorados": Column(int),
            "feridos": Column(int),
            "veiculos": Column(int),
            "latitude": Column(float),
            "longitude": Column(float),
            "regional": Column(str),
            "delegacia": Column(str),
            "uop": Column(str),
        }

    def extract(self, read_cache: bool = False):
        """M??todo para extra????o dos do hist??rico de acidentes

        Parameters
        ----------
        read_cache : bool, optional
            Ativa o modo de leitura de cache, by default False
        """

        logger.info(
            "In??cio da leitura dos registros de acidentes."
        ) if self.verbose else None

        # Carrega a cache caso o modo de leitura da cache esteja ativo:
        cache_path = PATH_DATA_CACHE_MODEL / f"{self.name}_raw.pkl"
        if read_cache:
            logger.info("Modo de leitura da cache ativo.")
            self.df = pd.read_pickle(cache_path)
            logger.info("Fim da extra????o dos dados.")
            return

        # Leitura dos registros dos acidentes:
        df = self.__read_accidents().pipe(trace_df)

        # Filtra a UF desejada:
        logger.info(
            f"Selecionando somente os dados do {self.uf}."
        ) if self.verbose else None
        df = df[df["uf"].str.upper() == self.uf].copy().pipe(trace_df)

        # Armazena a cache caso o modo de leitura da cache n??o esteja ativo:
        if not read_cache:
            logger.info(f"Armazenado {cache_path}.")
            df.to_pickle(cache_path)

        self.df = df.copy().pipe(trace_df)
        logger.info(f"Fim da extra????o dos dados.")

    def transform(self, read_cache: bool = False):
        """M??todo para pr??-processamento do hist??rico de acidentes

        Parameters
        ----------
        read_cache : bool, optional
            Ativa o modo de leitura de cache, by default False
        """

        logger.info("In??cio do pr?? processamento.") if self.verbose else None

        # Carrega a cache caso o modo de leitura da cache esteja ativo:
        cache_path = PATH_DATA_CACHE_MODEL / f"{self.name}.pkl"
        if read_cache:
            logger.info("Modo de leitura da cache ativo.")
            self.df = pd.read_pickle(cache_path)
            logger.info("Fim do pr??-processamento.")
            return

        df = self.df

        logger.info("Removendo registros incompletos.") if self.verbose else None
        df = df.dropna().pipe(trace_df).copy()

        df = (
            df.pipe(self.__filter_uf)
            .pipe(trace_df)
            .pipe(self.__create_datetime_column)
            .pipe(trace_df)
            .pipe(self.__classify_holiday_and_weekend)
            .pipe(trace_df)
        )

        logger.info("Padronizando os campos do tipo string.") if self.verbose else None
        df = clean_string(df, STR_COLS_TO_UPPER, "upper")
        df = clean_string(df, STR_COLS_TO_LOWER).pipe(trace_df)

        df = (
            df.pipe(self.__convert_lat_lon)
            .pipe(trace_df)
            .pipe(self.__keep_min_decimal_places)
            .pipe(trace_df)
            .pipe(self.__keep_geo_correct_rows)
            .pipe(trace_df)
            .pipe(self.__manual_transformations)
            .pipe(trace_df)
            .pipe(self.__remove_outlier_coords)
            .pipe(trace_df)
        )

        # Armazena a cache caso o modo de leitura da cache n??o esteja ativo:
        logger.info(f"Armazenado {cache_path}.")
        df.to_pickle(cache_path)

        self.df = df.copy()
        logger.info(f"Fim do pr??-processamento.") if self.verbose else None

    #######################################################################

    def __read_accidents(self) -> pd.DataFrame:
        """M??todo para carregar o hist??rico de acidetnes.

        Returns
        -------
        pd.DataFrame
            Hist??rico de acidentes.
        """
        logger.info("Lendo as urls dos acidentes.") if self.verbose else None
        with open(PATH_DATA_PRF / "accidents.json") as file:
            urls = json.load(file)

        df_out = pd.DataFrame()
        for year in urls.keys():

            # L?? os dados dos acidentes:
            url = urls[year]
            file_name = f"datatran{year}.csv"
            df = csv_zip_to_df(url, file_name)
            df["ano"] = year

            logger.info(
                f"Lendo os registros de acidentes de {year}."
            ) if self.verbose else None
            # Valida os dados de entrada:
            try:
                df = DataFrameSchema(
                    columns=self.df_schema_in,
                    unique=self.key_in,
                    coerce=True,
                    strict="filter",
                ).validate(df)
            except SchemaError as se:
                logger.error(f"Erro ao validar os dados dos acidentes de {year}.")
                logger.error(se)

            # Concatena os anos:
            if df_out.shape[0] == 0:
                df_out = df.copy()
            else:
                df_out = pd.concat([df_out, df], ignore_index=True)

        return df_out

    def __filter_uf(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para filtrar somente os registros nas delegacias da UF desejada.

        Parameters
        ----------
        df : pd.DataFrame
            Base de acidentes.

        Returns
        -------
        pd.DataFrame
            Base de acidentes filtrada.
        """
        logger.info(
            f"Mantendo somente os registros das delegacias do {self.uf}."
        ) if self.verbose else None

        df["delegacia"] = df["delegacia"].str.upper()

        df_out = df[
            df["delegacia"].str.contains("|".join([self.uf]))
        ].copy()  # fun????o preparada para receber m??ltiplas UFs

        return df_out

    def __create_datetime_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para cria????o do campo 'data_hora' e remo????o dos campos 'data_inversa' e 'hora'.

        Parameters
        ----------
        df : pd.DataFrame
            _description_

        Returns
        -------
        pd.DataFrame
            _description_
        """
        logger.info("Criando o campo data_hora.") if self.verbose else None
        df["data_hora"] = pd.to_datetime(df["data_inversa"] + " " + df["horario"])
        df.drop(columns=["data_inversa", "horario"], inplace=True)

        return df

    def __convert_lat_lon(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para convers??o do formato dos campos 'latitude' e 'longitude'.

        Parameters
        ----------
        df : pd.DataFrame
            Base de acidentes.

        Returns
        -------
        pd.DataFrame
            Base de acidentes com as convers??es realizadas.
        """
        logger.info(
            "Convertendo os tipos dos campos latitude e longitude."
        ) if self.verbose else None

        df["latitude"] = (df["latitude"].str.replace(",", ".")).astype(float)
        df["longitude"] = (df["longitude"].str.replace(",", ".")).astype(float)

        return df

    def __get_polygon(self):
        """M??todo para carregamento do json com as coordenadas e constru????o do pol??gono da regi??o de interesse.

        Returns
        -------
        _type_
            Pol??gono da regi??o de interesse.
        """
        with open(PATH_DATA_IBGE_BORDERS / f"{self.uf}.json") as file:
            borders = json.load(file)["borders"][0]

        lst_lon = [x["lng"] for x in borders]
        lst_lat = [x["lat"] for x in borders]
        polygon = Polygon(zip(lst_lon, lst_lat))

        return polygon

    def __within_polygon(self, lng: float, lat: float, polygon: Polygon) -> bool:
        """M??todo para identificar se um ponto est?? dentro de um pol??gono.

        Parameters
        ----------
        lng : float
            Longitude do ponto.
        lat : float
            Latitude do ponto.
        polygon : Polygon
            Pol??gono da regi??o de interesse.

        Returns
        -------
        bool
            Verdadeiro se o ponto est?? dentro do pol??gono. Falso, caso contr??rio.
        """
        point = Point(float(lng), float(lat))
        isin_polygon = point.within(polygon)

        return isin_polygon

    def __keep_min_decimal_places(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para garantir na base somente registros com coordenadas atendendo um n??mero m??nimo de casas decimais.

        Parameters
        ----------
        df : pd.DataFrame
            Data frame completo.

        Returns
        -------
        pd.DataFrame
            Data frame com os registros removidos.
        """
        logger.info(
            f"Eliminando registros com lat/lon com menos de {COORDS_MIN_DECIMAL_PLACES} casas decimais."
        ) if self.verbose else None

        mask_lat = get_decimal_places(df["latitude"]) >= COORDS_MIN_DECIMAL_PLACES
        mask_lon = get_decimal_places(df["longitude"]) >= COORDS_MIN_DECIMAL_PLACES
        df_out = df[mask_lat & mask_lon]

        return df_out

    def __keep_geo_correct_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para garantir registros ocorridos na regi??o geogr??fica de interesse.

        Parameters
        ----------
        df : pd.DataFrame
            Data frame completo.

        Returns
        -------
        pd.DataFrame
            Data frame com os registros removidos.
        """
        logger.info(
            f"Mantendo somente registros de acidentes ocorridos geograficamente no {self.uf}."
        ) if self.verbose else None

        polygon = self.__get_polygon()
        isin_polygon = df.apply(
            lambda x: self.__within_polygon(x.longitude, x.latitude, polygon), axis=1
        )

        df_out = df[isin_polygon].copy()

        return df_out

    def __remove_outlier_coords(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para remover registros de acidentes considerados outliers aos demais pontos alocados na mesma delegacia.

        Parameters
        ----------
        df : pd.DataFrame
            Data frame completo.

        Returns
        -------
        pd.DataFrame
            Data frame com outliers removidos.
        """
        logger.info(
            f"Eliminando as coordenadas outliers por delegacia."
        ) if self.verbose else None

        lat_abs_zscore = (
            df.groupby(["delegacia"])["latitude"]
            .transform(lambda x: stats.zscore(x, ddof=1))
            .abs()
        )
        lon_abs_zscore = (
            df.groupby(["delegacia"])["longitude"]
            .transform(lambda x: stats.zscore(x, ddof=1))
            .abs()
        )

        mask = (lat_abs_zscore <= 3) & (lon_abs_zscore <= 3)
        df_out = df[mask]

        return df_out

    def __manual_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para aplicar as corre????es necess??rias identificadas ap??s an??lise.

        Parameters
        ----------
        df : pd.DataFrame
            Data frame dos acidentes.

        Returns
        -------
        pd.DataFrame
            Data frame com as corre????es aplicadas.
        """
        logger.info(f"Aplica????o das corre????es manuais.") if self.verbose else None

        # L?? o json com as corre????es manuais:
        with open(PATH_DATA_PRF / "transformations.json") as file:
            transformations = json.load(file)

            accidents_to_delete_by_uop = transformations["accidents_deletion"]["uop"]
            uops_to_replace = transformations["accidents_replace"]["uop"]
            dels_to_replace = transformations["accidents_replace"]["del"]

        # Deleta os registros a serem desconsiderados:
        df_out = df[~df["uop"].isin(accidents_to_delete_by_uop)].copy()

        # Corrige os registros:
        right_dels = df_out["uop"].map(dels_to_replace)
        right_uops = df_out["uop"].map(uops_to_replace)
        df_out["delegacia"] = right_dels.combine_first(df_out["delegacia"])
        df_out["uop"] = right_uops.combine_first(df_out["uop"])

        return df_out

    def __classify_holiday_and_weekend(self, df: pd.DataFrame) -> pd.DataFrame:
        """M??todo para classificar feriados e finais de semana.

        Parameters
        ----------
        df : pd.DataFrame
            Data frame completo.

        Returns
        -------
        pd.DataFrame
            Data frame com a flag "is_holiday".
        """
        logger.info(
            "Criando as flags de feriado e final de semana."
        ) if self.verbose else None

        br_holidays = holidays.country_holidays("BR", subdiv=self.uf)
        df["is_holiday"] = ~(df["data_hora"].apply(br_holidays.get)).isna()

        df["is_weekend"] = df["data_hora"].dt.weekday >= 5

        return df
