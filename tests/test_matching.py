"""Tests unitarios para src/matching.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.matching import normalizar, es_composicion_auxiliar


def test_normalizar_simple():
    assert normalizar("Alvenaria") == "alvenaria"


def test_normalizar_compuesto():
    assert normalizar("Concreto Armado") == "concreto armado"


def test_normalizar_tildes():
    assert normalizar("Argamassa de Cimento") == "argamassa de cimento"


def test_normalizar_puntuacion():
    assert normalizar("fck=25 MPa, e=14 cm") == "fck 25 mpa e 14 cm"


def test_composicion_auxiliar_por_descripcion():
    assert es_composicion_auxiliar("06.103", "Argamassa mista de cimento, cal e areia") is True


def test_composicion_auxiliar_false():
    assert es_composicion_auxiliar("06.101", "Alvenaria estrutural com blocos ceramicos") is False


def test_composicion_auxiliar_concreto():
    assert es_composicion_auxiliar(None, "Concreto fck=25 MPa para vigas") is True


def test_composicion_auxiliar_por_subcapitulo():
    assert es_composicion_auxiliar("Argamassa de assentamento", "Alvenaria") is True


def test_composicion_auxiliar_subcapitulo_none():
    assert es_composicion_auxiliar(None, None) is False
