"""Country normalization + alias resolution tests."""

from __future__ import annotations

import pandas as pd

from data_harmonizer.transformations.country import CountryResolver, normalize_label


def test_normalize_label():
    assert normalize_label("  U.S.A. ") == "usa"
    assert normalize_label("United States of America") == "united states of america"
    assert normalize_label("GERMANY ") == "germany"


def test_country_alias_resolution():
    resolver = CountryResolver()
    assert resolver.resolve("USA") == ("UNITED STATES", "US", "USA", True)
    assert resolver.resolve("usa") == ("UNITED STATES", "US", "USA", True)
    assert resolver.resolve("U.S.A.") == ("UNITED STATES", "US", "USA", True)
    assert resolver.resolve("United States of America") == ("UNITED STATES", "US", "USA", True)
    assert resolver.resolve("GERMANY") == ("GERMANY", "DE", "DEU", True)
    assert resolver.resolve("Brasil") == ("BRAZIL", "BR", "BRA", True)


def test_iso_codes_resolve():
    resolver = CountryResolver()
    assert resolver.resolve("US")[3] is True
    assert resolver.resolve("US")[0] == "UNITED STATES"
    assert resolver.resolve("IN")[0] == "INDIA"


def test_unresolved_label_kept_and_flagged():
    resolver = CountryResolver()
    name, a2, a3, ok = resolver.resolve("Atlantis")
    assert ok is False
    assert name == "ATLANTIS"
    assert a2 is None and a3 is None


def test_resolve_series_records_lineage():
    resolver = CountryResolver()
    series = pd.Series(["usa", "Germany"], name="country")
    out, records = resolver.resolve_series(series, "src", "country")
    assert out["country_name"].tolist() == ["UNITED STATES", "GERMANY"]
    assert out["iso_alpha2"].tolist() == ["US", "DE"]
    assert len(records) == 2
    assert all(r.transformation_type.value == "COUNTRY_NORMALIZATION" for r in records)
    assert records[0].original_value == "usa"