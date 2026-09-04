#!/usr/bin/env bash
# Met commitlint.config.mjs sous test : les cinq exemples du doc 10 §1 doivent passer, les
# formes que ce document proscrit doivent échouer. Lancé par .github/workflows/commit-lint.yml
# et par « make lint » — le même contrôle des deux côtés, comme l'exige le doc 19 §6.
#
# Écrit pour GNU bash 3.2, la version que fournit macOS : ni tableaux associatifs, ni mapfile.
set -uo pipefail
cd "$(dirname "$0")/.."

# Les cinq exemples du doc 10 §1, puis trois cas que la configuration doit accepter sans que le
# document les cite : un nom propre en milieu de description, et les deux formes de pied.
valides=(
  "feat(api): ajoute l'endpoint de recherche avec facettes"
  "fix(scraping): corrige l'extraction de prix avec espace insécable"
  "refactor(api): extrait le scoring dans un service de domaine"
  "perf(db): ajoute un index partiel sur les offres en stock"
  "perf(db): partitionne price_history par mois"
  "feat(frontend): ajoute le client Orval généré depuis FastAPI"
  "chore(infra): met en place la ci"$'\n\n'"Refs KAR-10"
  "chore(db): partitionne price_history"$'\n\n'"Refs KAR-10"$'\n'"Refs ADR-0022"
)

# Chaque entrée viole une règle, sauf la première, qui n'a ni type, ni scope, ni description.
invalides=(
  "update stuff"
  "docs(adr): documente le choix du partitionnement"
  "feat(api): Ajoute l'endpoint de recherche avec facettes"
  "feat(api): ajoute l'endpoint de recherche avec facettes."
  "ci(infra): met en place le workflow de commitlint"
  "chore: configure commitlint"
)

code=0

for message in "${valides[@]}"; do
  if ! printf '%s\n' "$message" | pnpm exec commitlint --verbose; then
    printf 'ATTENDU VALIDE, REFUSÉ : %s\n' "${message%%$'\n'*}" >&2
    code=1
  fi
done

# La sortie est écartée : un refus est le résultat attendu, l'afficher ferait passer une
# exécution conforme pour une exécution en échec.
for message in "${invalides[@]}"; do
  if printf '%s\n' "$message" | pnpm exec commitlint >/dev/null 2>&1; then
    printf 'ATTENDU INVALIDE, ACCEPTÉ : %s\n' "${message%%$'\n'*}" >&2
    code=1
  fi
done

if [ "$code" -eq 0 ]; then
  printf '%s messages valides, %s refusés : conforme au doc 10 §1.\n' \
    "${#valides[@]}" "${#invalides[@]}"
fi

exit "$code"
