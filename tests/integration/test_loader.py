"""Integration tests for CellBulkLoader and operator metadata loader."""

from pathlib import Path
import pytest

from location_resolver.db.connection import get_connection
from location_resolver.db.loader import CellBulkLoader, IngestionStats, load_operator_networks
from location_resolver.db.migrator import apply_migrations
from location_resolver.domain.cell import Cell, RadioType


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure migrations are applied before running loader tests."""
    apply_migrations()
    yield
    # Clean up test rows
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cell_towers WHERE source = 'test_loader';")
            cur.execute("DELETE FROM operator_networks WHERE mcc = 998;")
        conn.commit()


def test_format_cell_copy_row():
    """Verify conversion of canonical Cell to COPY text TSV line."""
    cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=45,
        lac_tac=1234,
        cell_id=56789,
        unit=15,
        latitude=12.9716,
        longitude=77.5946,
        range_m=1500,
        samples=10,
        changeable=True,
        created_epoch=1600000000,
        updated_epoch=1600005000,
        average_signal=None,
        source="test_loader",
        source_dataset="test.csv",
    )

    row_str = CellBulkLoader.format_cell_copy_row(cell)
    cols = row_str.rstrip("\n").split("\t")

    assert len(cols) == 20
    assert cols[0] == "LTE"
    assert cols[1] == "404"
    assert cols[2] == "45"
    assert cols[3] == "1234"
    assert cols[4] == "56789"
    assert cols[5] == "15"
    assert cols[6] == "12.971600"
    assert cols[7] == "77.594600"
    assert cols[8] == "SRID=4326;POINT(77.594600 12.971600)"
    assert cols[9] == "1500"
    assert cols[10] == "f"  # not suspicious (< 50km)
    assert cols[11] == "10"
    assert cols[12] == "t"
    assert cols[17] == r"\N"  # average_signal null
    assert cols[18] == "test_loader"
    assert cols[19] == "test.csv"


def test_load_real_operator_networks_metadata():
    """Verify loading real MCC-MNC India.csv into operator_networks table."""
    real_csv = Path("/home/Krishna-Singh/Downloads/dataset-opencellmap/MCC-MNC India.csv")
    if not real_csv.exists():
        pytest.skip(f"MCC-MNC India.csv not found at {real_csv}")

    count = load_operator_networks(real_csv)
    assert count >= 90

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check Airtel Delhi (404, 10)
            cur.execute("SELECT operator_name, telecom_circle FROM operator_networks WHERE mcc = 404 AND mnc = 10;")
            row_airtel = cur.fetchone()
            assert row_airtel is not None
            assert "AirTel" in row_airtel[0]
            assert "Delhi" in row_airtel[1]

            # Check Jio (405, 854)
            cur.execute("SELECT operator_name, telecom_circle FROM operator_networks WHERE mcc = 405 AND mnc = 854;")
            row_jio = cur.fetchone()
            assert row_jio is not None
            assert "Jio" in row_jio[0]
            assert "Andhra Pradesh" in row_jio[1]


def test_stream_copy_batch_insertion():
    """Verify streaming a batch of canonical Cell objects directly to PostGIS via COPY."""
    cells = [
        Cell(
            radio=RadioType.GSM,
            mcc=404,
            mnc=10,
            lac_tac=310,
            cell_id=200001 + i,
            latitude=28.6000 + (i * 0.001),
            longitude=77.2000 + (i * 0.001),
            range_m=1000,
            samples=5,
            source="test_loader",
            source_dataset="batch_test.csv",
        )
        for i in range(10)
    ]

    loader = CellBulkLoader()
    inserted = loader.stream_copy_batch(cells)
    assert inserted == 10

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cell_towers WHERE source = 'test_loader' AND cell_id >= 200001;")
            cnt = cur.fetchone()
            assert cnt is not None
            assert cnt[0] == 10

            # Verify spatial query on newly inserted cell
            cur.execute("""
                SELECT cell_id, ST_AsText(location) 
                FROM cell_towers 
                WHERE radio = 'GSM' AND mcc = 404 AND mnc = 10 AND lac_tac = 310 AND cell_id = 200001;
            """)
            rec = cur.fetchone()
            assert rec is not None
            assert "POINT(77.2 28.6)" in rec[1]
