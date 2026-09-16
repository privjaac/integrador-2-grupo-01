-- ============================================================
-- PARTE 1: Tablas, claves primarias y claves foraneas
-- Traduccion literal del Diagrama Entidad-Relacion (seccion 5.3.2
-- del informe APF1), aprobado en la Unidad 1.
-- ============================================================

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    level INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL
);

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(120) NOT NULL,
    module VARCHAR(80) NOT NULL,
    action VARCHAR(80) NOT NULL
);

CREATE TABLE role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE TABLE collaborators (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    cupe VARCHAR(40) NOT NULL,
    username VARCHAR(80) NOT NULL,
    email VARCHAR(160) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL
);

CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    collaborator_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP
);

CREATE TABLE token_blacklist (
    id BIGSERIAL PRIMARY KEY,
    collaborator_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE password_reset_requests (
    id BIGSERIAL PRIMARY KEY,
    collaborator_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP
);

CREATE TABLE web_catalog (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    base_price NUMERIC(10, 2) NOT NULL CHECK (base_price > 0),
    active BOOLEAN NOT NULL
);

CREATE TABLE clients (
    id BIGSERIAL PRIMARY KEY,
    web_type_id BIGINT NOT NULL REFERENCES web_catalog(id) ON DELETE RESTRICT,
    created_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    cupe VARCHAR(40) NOT NULL,
    document VARCHAR(40) NOT NULL,
    plan VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL,
    delivery_date DATE
);

CREATE TABLE client_change_requests (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    requested_by_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE RESTRICT,
    approved_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    status VARCHAR(40) NOT NULL,
    before_json JSON NOT NULL,
    after_json JSON NOT NULL,
    reason TEXT
);

CREATE TABLE client_history (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    changed_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    before_json JSON,
    after_json JSON,
    changed_at TIMESTAMP
);

CREATE TABLE web_features (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    active BOOLEAN NOT NULL
);

CREATE TABLE client_features (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    web_feature_id BIGINT NOT NULL REFERENCES web_features(id) ON DELETE RESTRICT,
    assigned_price NUMERIC(10, 2) NOT NULL CHECK (assigned_price > 0),
    active BOOLEAN NOT NULL
);

CREATE TABLE cupe_logs (
    id BIGSERIAL PRIMARY KEY,
    changed_by_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE RESTRICT,
    entity_type VARCHAR(40) NOT NULL,
    entity_id INTEGER NOT NULL,
    old_cupe VARCHAR(40) NOT NULL,
    new_cupe VARCHAR(40) NOT NULL,
    changed_at TIMESTAMP NOT NULL
);

CREATE TABLE cupe_change_requests (
    id BIGSERIAL PRIMARY KEY,
    requested_by_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE RESTRICT,
    approved_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    entity_type VARCHAR(40) NOT NULL,
    entity_id INTEGER NOT NULL,
    old_cupe VARCHAR(40) NOT NULL,
    new_cupe VARCHAR(40) NOT NULL,
    status VARCHAR(40) NOT NULL
);

CREATE TABLE prospects (
    id BIGSERIAL PRIMARY KEY,
    converted_client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    name VARCHAR(160) NOT NULL,
    contact VARCHAR(160),
    status VARCHAR(40) NOT NULL,
    source VARCHAR(80)
);

CREATE TABLE prospect_notes (
    id BIGSERIAL PRIMARY KEY,
    prospect_id BIGINT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    created_by_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE RESTRICT,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE platforms (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    active BOOLEAN NOT NULL
);

CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform_id BIGINT REFERENCES platforms(id) ON DELETE SET NULL,
    responsible_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    name VARCHAR(160) NOT NULL,
    status VARCHAR(40) NOT NULL
);

CREATE TABLE collaborator_payments (
    id BIGSERIAL PRIMARY KEY,
    collaborator_id BIGINT NOT NULL REFERENCES collaborators(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    payment_date DATE,
    status VARCHAR(40) NOT NULL
);

CREATE TABLE notification_settings (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    channel VARCHAR(40) NOT NULL,
    days_before INTEGER,
    frequency VARCHAR(40) NOT NULL,
    active BOOLEAN NOT NULL
);

CREATE TABLE notification_logs (
    id BIGSERIAL PRIMARY KEY,
    notification_setting_id BIGINT NOT NULL REFERENCES notification_settings(id) ON DELETE CASCADE,
    entity_type VARCHAR(40) NOT NULL,
    entity_id INTEGER NOT NULL,
    channel VARCHAR(40) NOT NULL,
    status VARCHAR(40) NOT NULL,
    sent_at TIMESTAMP,
    error TEXT
);

-- ============================================================
-- PARTE 2: Restricciones UNIQUE / CHECK adicionales e indices B-Tree
-- Solo sobre columnas de busqueda frecuente ya usadas en la API real
-- (backend/api/routers/*.py). No se agregan CHECK de enumeracion en
-- tablas todavia no implementadas en codigo (prospects, projects,
-- notification_*, *_change_requests) porque esos valores de estado
-- aun no estan definidos en las reglas de negocio.
-- ============================================================

ALTER TABLE collaborators ADD CONSTRAINT uq_collaborators_cupe UNIQUE (cupe);
ALTER TABLE collaborators ADD CONSTRAINT uq_collaborators_username UNIQUE (username);
ALTER TABLE collaborators ADD CONSTRAINT uq_collaborators_email UNIQUE (email);

ALTER TABLE clients ADD CONSTRAINT uq_clients_cupe UNIQUE (cupe);
ALTER TABLE clients ADD CONSTRAINT uq_clients_document UNIQUE (document);

ALTER TABLE roles ADD CONSTRAINT uq_roles_name UNIQUE (name);
ALTER TABLE web_catalog ADD CONSTRAINT uq_web_catalog_name UNIQUE (name);
ALTER TABLE web_features ADD CONSTRAINT uq_web_features_name UNIQUE (name);
ALTER TABLE client_features ADD CONSTRAINT uq_client_features_pair UNIQUE (client_id, web_feature_id);
ALTER TABLE role_permissions ADD CONSTRAINT uq_role_permissions_pair UNIQUE (role_id, permission_id);

CREATE INDEX idx_collaborators_is_active ON collaborators (is_active);
CREATE INDEX idx_collaborators_role_id ON collaborators (role_id);

CREATE INDEX idx_clients_status ON clients (status);
CREATE INDEX idx_clients_web_type_id ON clients (web_type_id);

CREATE INDEX idx_web_catalog_active ON web_catalog (active);
CREATE INDEX idx_web_features_active ON web_features (active);

CREATE INDEX idx_cupe_logs_entity ON cupe_logs (entity_type, entity_id);
CREATE INDEX idx_cupe_change_requests_entity ON cupe_change_requests (entity_type, entity_id);
CREATE INDEX idx_client_change_requests_client_id ON client_change_requests (client_id);
CREATE INDEX idx_notification_logs_entity ON notification_logs (entity_type, entity_id);
CREATE INDEX idx_prospects_status ON prospects (status);
CREATE INDEX idx_projects_client_id ON projects (client_id);
