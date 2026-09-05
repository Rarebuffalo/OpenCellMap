"""Integration tests for PostgreSQL + PostGIS database schema and spatial queries."""

import pytest
import psycopg
from location_resolver.config import settings
from location_resolver.db.connection import get_connection
from location_resolver.db.migrator import apply_migrations
from location_resolver.domain.cell import Cell, RadioType


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure migrations are applied before running integration tests."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except Exception as exc:
        pytest.skip(f"PostgreSQL/PostGIS container not reachable on port {settings.POSTGRES_PORT}: {exc}")

    apply_migrations()
    yield
    # Clean up test rows after module tests
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cell_towers WHERE source = 'test_integration';")
            cur.execute("DELETE FROM operator_networks WHERE mcc = 999;")
        conn.commit()


def test_schema_tables_and_postgis_extension():
    """Verify PostGIS extension and core tables exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT PostGIS_Version();")
            res = cur.fetchone()
            assert res is not None
            version = res[0]
            assert "3." in version

            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = {row[0] for row in cur.fetchall()}
            assert "cell_towers" in tables
            assert "operator_networks" in tables
            assert "schema_migrations" in tables


def test_insert_canonical_cell_and_exact_lookup():
    """Verify inserting a canonical Cell entity and querying by exact composite key."""
    cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=45,
        lac_tac=25033,
        cell_id=53132,
        unit=12,
        latitude=12.903442,
        longitude=77.543466,
        range_m=1369,
        samples=14,
        changeable=True,
        created_epoch=1459703141,
        updated_epoch=1491232540,
        average_signal=None,  # Null signal
        source="test_integration",
        source_dataset="404.csv",
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Clean if exists
            cur.execute("""
                DELETE FROM cell_towers 
                WHERE radio = %s AND mcc = %s AND mnc = %s AND lac_tac = %s AND cell_id = %s;
            """, (cell.radio.value, cell.mcc, cell.mnc, cell.lac_tac, cell.cell_id))

            # Insert cell using ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            cur.execute("""
                INSERT INTO cell_towers (
                    radio, mcc, mnc, lac_tac, cell_id, unit,
                    latitude, longitude, location,
                    range_m, is_suspicious_range, samples, changeable,
                    created_at, updated_at, created_epoch, updated_epoch,
                    average_signal, source, source_dataset
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                ) RETURNING id;
            """, (
                cell.radio.value, cell.mcc, cell.mnc, cell.lac_tac, cell.cell_id, cell.unit,
                cell.latitude, cell.longitude, cell.longitude, cell.latitude,
                cell.range_m, cell.range_m > 50000, cell.samples, cell.changeable,
                cell.created_at, cell.updated_at, cell.created_epoch, cell.updated_epoch,
                cell.average_signal, cell.source, cell.source_dataset,
            ))
            tower_id = cur.fetchone()[0]
            assert tower_id > 0

            # Query exact match
            cur.execute("""
                SELECT radio, mcc, mnc, lac_tac, cell_id, latitude, longitude,
                       average_signal, is_suspicious_range, ST_AsText(location)
                FROM cell_towers 
                WHERE radio = %s AND mcc = %s AND mnc = %s AND lac_tac = %s AND cell_id = %s;
            """, (cell.radio.value, cell.mcc, cell.mnc, cell.lac_tac, cell.cell_id))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "LTE"
            assert row[1] == 404
            assert row[2] == 45
            assert row[3] == 25033
            assert row[4] == 53132
            assert row[5] == pytest.approx(12.903442)
            assert row[6] == pytest.approx(77.543466)
            assert row[7] is None  # NULL signal preserved
            assert row[8] is False  # not suspicious range
            assert "POINT(77.543466 12.903442)" in row[9]

        conn.commit()


def test_duplicate_cellular_identity_rejected():
    """Verify unique constraint on (radio, mcc, mnc, lac_tac, cell_id) rejects duplicates."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.UniqueViolation):
                # Attempt to insert identical composite key
                cur.execute("""
                    INSERT INTO cell_towers (
                        radio, mcc, mnc, lac_tac, cell_id,
                        latitude, longitude, location, source
                    ) VALUES (
                        'LTE', 404, 45, 25033, 53132,
                        12.903442, 77.543466, ST_SetSRID(ST_MakePoint(77.543466, 12.903442), 4326),
                        'test_integration'
                    );
                """)
        conn.rollback()


def test_spatial_query_within_radius():
    """Verify spatial query finding towers within radius using ST_DWithin on geography."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Query within 2km of Bengaluru coordinates (77.5434, 12.9034)
            cur.execute("""
                SELECT radio, cell_id, 
                       ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(77.5434, 12.9034), 4326)::geography) AS distance_meters
                FROM cell_towers 
                WHERE ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(77.5434, 12.9034), 4326)::geography, 2000.0)
                  AND source = 'test_integration';
            """)
            rows = cur.fetchall()
            assert len(rows) >= 1
            cell_id, distance_m = rows[0][1], rows[0][2]
            assert cell_id == 53132
            assert distance_m < 2000.0


def test_suspicious_range_preservation():
    """Verify range > 50km is preserved and flagged with is_suspicious_range = TRUE."""
    cell = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=999,
        cell_id=88888,
        latitude=28.6139,
        longitude=77.2090,
        range_m=75000,  # 75km suspicious range
        source="test_integration",
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cell_towers (
                    radio, mcc, mnc, lac_tac, cell_id,
                    latitude, longitude, location,
                    range_m, is_suspicious_range, source
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s, %s, %s
                ) RETURNING range_m, is_suspicious_range;
            """, (
                cell.radio.value, cell.mcc, cell.mnc, cell.lac_tac, cell.cell_id,
                cell.latitude, cell.longitude, cell.longitude, cell.latitude,
                cell.range_m, cell.range_m > 50000, cell.source,
            ))
            res_range_row = cur.fetchone()
            assert res_range_row is not None
            res_range, is_suspicious = res_range_row[0], res_range_row[1]
            assert res_range == 75000
            assert is_suspicious is True
        conn.commit()


def test_operator_networks_table_insert_and_lookup():
    """Verify operator_networks table handles MCC-MNC circle metadata."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO operator_networks (mcc, mnc, operator_name, telecom_circle)
                VALUES (999, 1, 'Test Telecom', 'Delhi & NCR')
                ON CONFLICT (mcc, mnc) DO UPDATE SET operator_name = EXCLUDED.operator_name;
            """)
            cur.execute("SELECT operator_name, telecom_circle FROM operator_networks WHERE mcc = 999 AND mnc = 1;")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "Test Telecom"
            assert row[1] == "Delhi & NCR"
        conn.commit()
