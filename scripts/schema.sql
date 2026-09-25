PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE dataset (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    name TEXT NOT NULL,
    model_scope TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE source (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    path TEXT NOT NULL,
    url TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE TABLE assessment_definition (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    name TEXT NOT NULL,
    year INTEGER NOT NULL,
    level TEXT NOT NULL CHECK(level IN ('ES','HS')),
    grades TEXT NOT NULL,
    standard TEXT NOT NULL,
    source_url TEXT NOT NULL
);
CREATE TABLE economic_definition (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    definition TEXT NOT NULL,
    source_url TEXT NOT NULL
);
-- IDs belong to a source namespace. No name-based CPS/RCDTS crosswalk is inferred.
CREATE TABLE school (
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    school_id TEXT NOT NULL,
    name TEXT,
    district_id TEXT,
    district_name TEXT,
    city TEXT,
    county TEXT,
    profile_json TEXT,
    source_id TEXT NOT NULL REFERENCES source(id),
    source_order INTEGER NOT NULL,
    PRIMARY KEY(dataset_id, school_id)
);
CREATE TABLE economic_observation (
    dataset_id TEXT NOT NULL,
    school_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    definition_id TEXT NOT NULL REFERENCES economic_definition(id),
    name TEXT,
    enrollment REAL CHECK(enrollment IS NULL OR enrollment >= 0),
    low_income REAL CHECK(low_income IS NULL OR low_income >= 0),
    percentage REAL CHECK(percentage IS NULL OR percentage BETWEEN 0 AND 100),
    source_label TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(id),
    source_order INTEGER NOT NULL,
    PRIMARY KEY(dataset_id, school_id, year),
    FOREIGN KEY(dataset_id, school_id) REFERENCES school(dataset_id, school_id),
    CHECK(low_income IS NULL OR enrollment IS NULL OR low_income <= enrollment)
);
CREATE TABLE assessment_observation (
    dataset_id TEXT NOT NULL,
    school_id TEXT NOT NULL,
    definition_id TEXT NOT NULL REFERENCES assessment_definition(id),
    subject TEXT NOT NULL CHECK(subject IN ('math','reading')),
    proficiency REAL CHECK(proficiency IS NULL OR proficiency BETWEEN 0 AND 100),
    tested INTEGER CHECK(tested IS NULL OR tested >= 0),
    status TEXT NOT NULL CHECK(status IN ('reported','not_reported','suppressed_or_not_reported')),
    raw_value TEXT,
    raw_tested TEXT,
    source_id TEXT NOT NULL REFERENCES source(id),
    source_order INTEGER NOT NULL,
    PRIMARY KEY(dataset_id, school_id, definition_id, subject),
    FOREIGN KEY(dataset_id, school_id) REFERENCES school(dataset_id, school_id)
);
CREATE TABLE model_run (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES dataset(id),
    definition_id TEXT NOT NULL REFERENCES assessment_definition(id),
    subject TEXT NOT NULL,
    method_version TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    summary_json TEXT NOT NULL
);
CREATE TABLE model_result (
    model_id TEXT NOT NULL REFERENCES model_run(id) ON DELETE CASCADE,
    dataset_id TEXT NOT NULL,
    school_id TEXT NOT NULL,
    actual REAL NOT NULL,
    predicted REAL NOT NULL,
    studentized REAL NOT NULL,
    low REAL,
    high REAL,
    PRIMARY KEY(model_id, school_id),
    FOREIGN KEY(dataset_id, school_id) REFERENCES school(dataset_id, school_id)
);
CREATE INDEX assessment_by_dataset ON assessment_observation(dataset_id, definition_id);
