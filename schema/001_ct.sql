-- The `ct` database: the impersonations this project imagines, and what Certificate Transparency says about them.
-- Lives in the NSM lab's ClickHouse container alongside `nsm` and `ep` (CLAUDE.md C2). The lab's own data is untouched.
CREATE DATABASE IF NOT EXISTS ct;

-- Every name the generator can think of for a brand. Written once and cheaply — generating costs no requests — so the
-- table is the full imagined space, and `ct.checks` records how much of it has actually been asked about.
CREATE TABLE IF NOT EXISTS ct.candidates
(
    `domain`       String,                    -- what is asked about: punycode where the name is not ASCII
    `display`      String,                    -- what a reader would see: differs from `domain` only for homoglyphs
    `brand`        LowCardinality(String),
    `label`        LowCardinality(String),    -- the watchlist term it was built from
    `klass`        LowCardinality(String),    -- homoglyph | hyphen | combosquat | typo | tld
    `note`         String,                    -- how it was made, in words
    `generated_at` DateTime('UTC')
)
ENGINE = ReplacingMergeTree(generated_at)
ORDER BY domain;

-- One row per question asked of crt.sh. Keeping the misses matters as much as the hits: "no certificate exists for
-- this name" is a finding that decays, and without a timestamp there is no way to know how stale it is.
CREATE TABLE IF NOT EXISTS ct.checks
(
    `domain`           String,
    `checked_at`       DateTime('UTC'),
    `status`           LowCardinality(String),   -- found | absent | error
    `certificates`     UInt32,
    `first_not_before` DateTime('UTC'),
    `last_not_before`  DateTime('UTC'),
    `max_crtsh_id`     UInt64,
    `seconds`          Float32,
    `detail`           String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(checked_at)
ORDER BY (domain, checked_at)
TTL checked_at + INTERVAL 24 MONTH;

-- The certificates themselves, one row per (name, certificate). A certificate with five subject alternative names
-- produces five rows, because the name is what this project reasons about.
CREATE TABLE IF NOT EXISTS ct.certificates
(
    `name`          String,
    `crtsh_id`      UInt64,
    `candidate`     String,                    -- the candidate whose lookup returned it
    `brand`         LowCardinality(String),
    `common_name`   String,
    `issuer_name`   String,
    `issuer_ca_id`  UInt32,
    `serial_number` String,
    `not_before`    DateTime('UTC'),
    `not_after`     DateTime('UTC'),
    `ingested_at`   DateTime('UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (name, crtsh_id)
TTL ingested_at + INTERVAL 24 MONTH;
