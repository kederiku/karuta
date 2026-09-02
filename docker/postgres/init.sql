-- Joué par l'entrypoint PostgreSQL à la seule initialisation d'une grappe vide : les
-- extensions existent donc avant la première migration. Les recréer depuis une
-- migration supposerait un rôle applicatif superutilisateur.
-- La configuration de recherche fr_unaccent et les types énumérés relèvent de la
-- migration 001, pas de ce fichier (doc 04 §3).

-- Fonctions de hachage et de chiffrement côté base.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Recherche floue sur les libellés, par similarité de trigrammes.
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Comparaison de chaînes indépendante des accents.
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Index GIN mêlant colonnes scalaires et colonnes indexées par trigrammes.
CREATE EXTENSION IF NOT EXISTS "btree_gin";
