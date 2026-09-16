CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    level VARCHAR(2) NOT NULL UNIQUE CHECK (level IN ('L1', 'L2', 'L3', 'L4', 'L5')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE collaborators (
    id BIGSERIAL PRIMARY KEY,
    cupe VARCHAR(15) UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    document_type VARCHAR(20) NOT NULL DEFAULT 'DNI' CHECK (document_type IN ('DNI', 'Pasaporte', 'CE')),
    document_number VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    phone VARCHAR(20),
    city VARCHAR(50) NOT NULL DEFAULT 'Lima' CHECK (city IN ('Lima', 'Arequipa', 'Cusco', 'Trujillo', 'Piura', 'Ica')),
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id BIGINT REFERENCES roles(id) ON DELETE RESTRICT,
    area VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_collaborators_is_active ON collaborators (is_active);
CREATE INDEX idx_collaborators_role_id ON collaborators (role_id);

CREATE TABLE web_catalog (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    base_price_rent NUMERIC(8, 2) NOT NULL CHECK (base_price_rent > 0),
    base_price_sale NUMERIC(8, 2) NOT NULL CHECK (base_price_sale > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_web_catalog_is_active ON web_catalog (is_active);

CREATE TABLE clients (
    id BIGSERIAL PRIMARY KEY,
    cupe VARCHAR(15) UNIQUE,
    name VARCHAR(200) NOT NULL,
    document_type VARCHAR(10) NOT NULL DEFAULT 'DNI' CHECK (document_type IN ('DNI', 'RUC')),
    document_number VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(254),
    phone VARCHAR(20),
    web_type_id BIGINT NOT NULL REFERENCES web_catalog(id) ON DELETE RESTRICT,
    plan VARCHAR(10) NOT NULL DEFAULT 'alquiler' CHECK (plan IN ('alquiler', 'venta')),
    status VARCHAR(15) NOT NULL DEFAULT 'desarrollo' CHECK (status IN ('activo', 'desarrollo', 'inactivo')),
    base_price NUMERIC(10, 2) CHECK (base_price IS NULL OR base_price >= 0),
    initial_payment NUMERIC(10, 2) CHECK (initial_payment IS NULL OR initial_payment >= 0),
    extra_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (extra_price >= 0),
    total_price NUMERIC(10, 2) CHECK (total_price IS NULL OR total_price >= 0),
    registration_date DATE,
    delivery_date DATE,
    next_payment_date DATE,
    payment_frequency VARCHAR(10) CHECK (payment_frequency IN ('mensual', 'anual')),
    domain_price NUMERIC(8, 2) CHECK (domain_price IS NULL OR domain_price >= 0),
    notes TEXT,
    created_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clients_status ON clients (status);
CREATE INDEX idx_clients_web_type_id ON clients (web_type_id);
CREATE INDEX idx_clients_created_by_id ON clients (created_by_id);

CREATE TABLE web_features (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    extra_price NUMERIC(8, 2) NOT NULL CHECK (extra_price > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_web_features_is_active ON web_features (is_active);

CREATE TABLE client_features (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    feature_id BIGINT NOT NULL REFERENCES web_features(id) ON DELETE RESTRICT,
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, feature_id)
);

CREATE TABLE cupe_logs (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('client', 'collaborator')),
    entity_id INTEGER NOT NULL,
    old_cupe VARCHAR(15) NOT NULL,
    new_cupe VARCHAR(15) NOT NULL,
    reason VARCHAR(30) NOT NULL CHECK (reason IN ('error_generacion', 'reingreso', 'correccion_admin', 'otro')),
    observations TEXT,
    changed_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    authorized_by_id BIGINT REFERENCES collaborators(id) ON DELETE SET NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cupe_logs_entity ON cupe_logs (entity_type, entity_id);
