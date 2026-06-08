-- ═══════════════════════════════════════════════════════════════════════════════
-- SMART TRAFFIC MONITORING SYSTEM (STMS) — PostgreSQL Schema Initialization
-- ═══════════════════════════════════════════════════════════════════════════════
-- 
-- This SQL file defines the complete database schema for STMS.
-- It can be executed directly in PostgreSQL to set up the database.
-- 
-- TABLES (in dependency order):
--   1. user_account    (no dependencies)
--   2. camera          (no dependencies)
--   3. vehicle_detection (FK → camera)
--   4. traffic_density (FK → camera)
--   5. alert           (FK → traffic_density, camera)
-- 
-- IMPORTANT: This file is used for documentation and manual setup only.
-- In production, database creation is handled by SQLAlchemy ORM (models.py).
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 1: user_account
-- ─────────────────────────────────────────────────────────────────────────────
-- Stores user credentials and role-based access control.
-- password_hash: Bcrypt hashed password (cost ≥ 12)
-- role: Must be one of: supervisor, management, admin
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_account (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    CONSTRAINT check_user_role CHECK (role IN ('supervisor', 'management', 'admin'))
);

CREATE INDEX IF NOT EXISTS idx_user_username ON user_account(username);


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 2: camera
-- ─────────────────────────────────────────────────────────────────────────────
-- Represents traffic monitoring points (cameras/sensors).
-- direction: Specifies the traffic flow direction at this camera
-- status: Operational status (active, inactive, maintenance)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS camera (
    camera_id VARCHAR(20) PRIMARY KEY,
    location_name VARCHAR(100) NOT NULL,
    segment_id VARCHAR(20),
    road_capacity INTEGER NOT NULL DEFAULT 50,
    direction VARCHAR(20) NOT NULL DEFAULT 'Bidirectional',
    status VARCHAR(10) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_camera_direction CHECK (direction IN ('Inbound', 'Outbound', 'Bidirectional')),
    CONSTRAINT check_camera_status CHECK (status IN ('active', 'inactive', 'maintenance')),
    CONSTRAINT check_camera_capacity CHECK (road_capacity > 0)
);

CREATE INDEX IF NOT EXISTS idx_camera_status ON camera(status);


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 3: vehicle_detection
-- ─────────────────────────────────────────────────────────────────────────────
-- Records individual vehicle detection events from YOLOv8 model.
-- vehicle_type: Category of vehicle (Car, Motorcycle, Truck, Bus, Unknown)
-- confidence: Model confidence score (0.0-1.0)
-- bbox_data: Bounding box coordinates stored as JSON
-- ON DELETE CASCADE: If camera is deleted, all its detections are deleted
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS vehicle_detection (
    detection_id BIGSERIAL PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL REFERENCES camera(camera_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    direction VARCHAR(10) NOT NULL,
    bbox_data JSONB,
    confidence FLOAT,
    CONSTRAINT check_detection_count CHECK (count >= 0),
    CONSTRAINT check_detection_confidence CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    CONSTRAINT check_detection_direction CHECK (direction IN ('Inbound', 'Outbound')),
    CONSTRAINT check_detection_vehicle_type CHECK (vehicle_type IN ('Car', 'Motorcycle', 'Truck', 'Bus', 'Unknown'))
);

CREATE INDEX IF NOT EXISTS idx_detection_camera_timestamp ON vehicle_detection(camera_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_detection_timestamp ON vehicle_detection(timestamp);


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 4: traffic_density
-- ─────────────────────────────────────────────────────────────────────────────
-- Aggregated traffic metrics calculated at regular intervals (default: 15 min).
-- density_ratio: Ratio of vehicles to road capacity (0.0-1.0)
-- density_level: Classification based on thresholds (Low, Medium, High)
-- ON DELETE CASCADE: If camera is deleted, all its density records are deleted
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS traffic_density (
    density_id BIGSERIAL PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL REFERENCES camera(camera_id) ON DELETE CASCADE,
    interval_start TIMESTAMP NOT NULL,
    interval_end TIMESTAMP NOT NULL,
    total_vehicles INTEGER NOT NULL DEFAULT 0,
    inflow_count INTEGER NOT NULL DEFAULT 0,
    outflow_count INTEGER NOT NULL DEFAULT 0,
    density_ratio FLOAT,
    density_level VARCHAR(10) NOT NULL,
    CONSTRAINT check_density_total CHECK (total_vehicles >= 0),
    CONSTRAINT check_density_inflow CHECK (inflow_count >= 0),
    CONSTRAINT check_density_outflow CHECK (outflow_count >= 0),
    CONSTRAINT check_density_ratio CHECK (density_ratio IS NULL OR (density_ratio >= 0.0 AND density_ratio <= 1.0)),
    CONSTRAINT check_density_level CHECK (density_level IN ('Low', 'Medium', 'High'))
);

CREATE INDEX IF NOT EXISTS idx_density_camera_interval ON traffic_density(camera_id, interval_start, interval_end);
CREATE INDEX IF NOT EXISTS idx_density_level ON traffic_density(density_level);
CREATE INDEX IF NOT EXISTS idx_density_interval_start ON traffic_density(interval_start);


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 5: alert
-- ─────────────────────────────────────────────────────────────────────────────
-- Traffic alerts triggered when density level is HIGH.
-- 
-- UNIQUE CONSTRAINT on density_id:
--   This enforces a 1:1 relationship between ALERT and TRAFFIC_DENSITY.
--   It prevents duplicate alerts for the same density measurement.
--   
--   Example: If density_id=100 gets HIGH level, it creates alert_id=1.
--            If another HIGH density occurs at density_id=101, it creates alert_id=2.
--            But density_id=100 can NEVER have more than ONE alert.
--
-- acknowledged_at, acknowledged_by: Populated when supervisor acknowledges alert
-- ON DELETE CASCADE: If density or camera is deleted, alert is deleted
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alert (
    alert_id BIGSERIAL PRIMARY KEY,
    density_id BIGINT NOT NULL UNIQUE REFERENCES traffic_density(density_id) ON DELETE CASCADE,
    camera_id VARCHAR(20) NOT NULL REFERENCES camera(camera_id) ON DELETE CASCADE,
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    density_level VARCHAR(10) NOT NULL DEFAULT 'High',
    alert_type VARCHAR(50) NOT NULL DEFAULT 'High Density',
    severity VARCHAR(20) NOT NULL DEFAULT 'High',
    message VARCHAR(500) NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100),
    CONSTRAINT check_alert_density_level CHECK (density_level IN ('Low', 'Medium', 'High')),
    CONSTRAINT check_alert_severity CHECK (severity IN ('Low', 'Medium', 'High')),
    CONSTRAINT check_alert_acknowledged_consistency CHECK (
        (acknowledged = FALSE AND acknowledged_at IS NULL AND acknowledged_by IS NULL) OR
        (acknowledged = TRUE AND acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_alert_camera_triggered ON alert(camera_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_alert_acknowledged ON alert(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alert_density_id ON alert(density_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- DEFAULT DATA INSERTION
-- ═══════════════════════════════════════════════════════════════════════════════
-- Create default admin user for system initialization.
-- 
-- IMPORTANT: Replace '$2b$12$PLACEHOLDER_HASH' with actual bcrypt hash!
-- 
-- To generate a bcrypt hash in Python:
--   from passlib.context import CryptContext
--   pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
--   hash_value = pwd_context.hash("Admin@STMS2025")
--   print(hash_value)  # e.g., $2b$12$4K3f...
-- 
-- Then replace the PLACEHOLDER_HASH below with the generated hash.
-- ═══════════════════════════════════════════════════════════════════════════════

-- INSERT INTO user_account (user_id, username, password_hash, role)
-- VALUES ('admin-001', 'admin', '$2b$12$PLACEHOLDER_HASH_REPLACE_THIS', 'admin')
-- ON CONFLICT (username) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════════
-- SUMMARY
-- ═══════════════════════════════════════════════════════════════════════════════
-- Tables created: 5
--   ✓ user_account: User credentials & RBAC
--   ✓ camera: Monitoring points
--   ✓ vehicle_detection: Individual detections
--   ✓ traffic_density: Aggregated metrics
--   ✓ alert: Alert tracking with 1:1 density relation
-- 
-- Constraints enforced:
--   ✓ Foreign keys with CASCADE delete
--   ✓ CHECK constraints for valid ranges
--   ✓ UNIQUE constraint on alert.density_id (1:1 relation)
--   ✓ Indices for query optimization
-- 
-- Ready for production use with SQLAlchemy ORM!
-- ═══════════════════════════════════════════════════════════════════════════════
