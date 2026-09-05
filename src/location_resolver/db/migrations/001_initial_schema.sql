-- ==============================================================================
-- Open Location Resolution Infrastructure - Schema Migration 001
-- Initial PostGIS Schema for Cellular Towers and Operator Metadata
-- ==============================================================================

-- 1. Enable PostGIS Spatial Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Cellular Base Stations Table
CREATE TABLE IF NOT EXISTS cell_towers (
    id BIGSERIAL PRIMARY KEY,
    
    -- Cellular Network Identifiers
    radio VARCHAR(10) NOT NULL,
    mcc INTEGER NOT NULL,
    mnc INTEGER NOT NULL,
    lac_tac INTEGER NOT NULL,
    cell_id INTEGER NOT NULL,
    unit INTEGER NULL,
    
    -- Geographic Coordinates & PostGIS Spatial Geometry
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    
    -- Coverage Estimation & Quality Flags
    range_m INTEGER NOT NULL DEFAULT 1000,
    is_suspicious_range BOOLEAN NOT NULL DEFAULT FALSE,
    samples INTEGER NOT NULL DEFAULT 1,
    changeable BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Observation Timestamps & Epochs
    created_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NULL,
    created_epoch BIGINT NULL,
    updated_epoch BIGINT NULL,
    
    -- Signal Strength
    average_signal INTEGER NULL,
    
    -- Ingestion Provenance
    source VARCHAR(64) NOT NULL DEFAULT 'unknown',
    source_dataset VARCHAR(128) NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT uq_cell_towers_composite_key UNIQUE (radio, mcc, mnc, lac_tac, cell_id),
    CONSTRAINT chk_cell_towers_latitude CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT chk_cell_towers_longitude CHECK (longitude >= -180.0 AND longitude <= 180.0),
    CONSTRAINT chk_cell_towers_mcc CHECK (mcc > 0),
    CONSTRAINT chk_cell_towers_mnc CHECK (mnc >= 0),
    CONSTRAINT chk_cell_towers_lac_tac CHECK (lac_tac > 0),
    CONSTRAINT chk_cell_towers_cell_id CHECK (cell_id > 0)
);

-- 3. Dedicated Indexes for Query Performance
-- Spatial GIST Index for Geographic Radius / Bounding Box Lookups (ST_DWithin, ST_Contains)
CREATE INDEX IF NOT EXISTS idx_cell_towers_spatial 
    ON cell_towers USING GIST (location);

-- Operator-level lookup index (e.g. filtering all cells for Airtel / Jio in a circle)
CREATE INDEX IF NOT EXISTS idx_cell_towers_mcc_mnc 
    ON cell_towers (mcc, mnc);

-- Area-level lookup index (e.g. filtering all cells in a single LAC/TAC)
CREATE INDEX IF NOT EXISTS idx_cell_towers_lac 
    ON cell_towers (mcc, mnc, lac_tac);

-- 4. Operator Network Metadata Table (MCC-MNC Mapping)
CREATE TABLE IF NOT EXISTS operator_networks (
    mcc INTEGER NOT NULL,
    mnc INTEGER NOT NULL,
    operator_name VARCHAR(128) NOT NULL,
    telecom_circle VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (mcc, mnc),
    CONSTRAINT chk_operator_mcc CHECK (mcc > 0),
    CONSTRAINT chk_operator_mnc CHECK (mnc >= 0)
);
