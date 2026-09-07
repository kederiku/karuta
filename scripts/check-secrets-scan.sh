#!/usr/bin/env bash
# Met le scan de secrets sous test : un scanner qui ne trouve rien est indiscernable d'un scanner
# qui n'a rien lu, et c'est la seule des deux situations qui se voit dans un journal. Ce script
# prouve que le binaire détecte, et que la version qu'exécute la CI est bien celle du hook
# pre-commit. Lancé par .github/workflows/secrets-scan.yml et, pour son seul volet de version, par
# « make lint » — même contrôle des deux côtés, comme l'exige le doc 19 §6.
#
# --versions-only sert ce dernier cas : Gitleaks n'est pas une dépendance du projet et n'est donc
# pas présent sur un poste fraîchement cloné, alors que la comparaison de versions, elle, ne lit
# que deux fichiers. Rendre « make lint » tributaire d'un binaire absent le ferait échouer partout.
#
# Écrit pour GNU bash 3.2, la version que fournit macOS : ni tableaux associatifs, ni mapfile.
set -uo pipefail
cd "$(dirname "$0")/.."

GITLEAKS="${GITLEAKS:-gitleaks}"
workflow=.github/workflows/secrets-scan.yml
precommit=.pre-commit-config.yaml
code=0

# Deux versions de Gitleaks, ce sont deux jeux de règles : un secret arrêté en local passerait en
# CI, ou l'inverse. Les deux fichiers sont nommés dans le message pour que la correction soit
# évidente sans relire ce script.
ci_version=$(sed -n 's/^ *GITLEAKS_VERSION: *"\(.*\)" *$/\1/p' "$workflow")
ci_archive=$(sed -n 's/^ *GITLEAKS_ARCHIVE: *\(.*\) *$/\1/p' "$workflow")
hook_version=$(awk '
  /repo: https:\/\/github.com\/gitleaks\/gitleaks/ { found = 1; next }
  found && /rev:/ { sub(/^v/, "", $2); print $2; exit }
' "$precommit")

if [ -z "$ci_version" ]; then
  printf 'GITLEAKS_VERSION introuvable dans %s\n' "$workflow" >&2
  code=1
elif [ "$ci_version" != "$hook_version" ]; then
  printf 'VERSIONS DIVERGENTES : %s porte %s, %s porte %s\n' \
    "$workflow" "$ci_version" "$precommit" "$hook_version" >&2
  code=1
fi

# L'archive porte le numéro de version dans son nom : la désaccorder du reste ferait télécharger
# une version dont l'empreinte, elle, ne correspondrait plus — échec tardif et obscur.
case "$ci_archive" in
  *"_${ci_version}_"*) ;;
  *)
    printf 'ARCHIVE INCOHÉRENTE : %s ne porte pas la version %s\n' "$ci_archive" "$ci_version" >&2
    code=1
    ;;
esac

if [ "${1:-}" = "--versions-only" ]; then
  [ "$code" -eq 0 ] && printf 'Gitleaks %s : CI et pre-commit accordés.\n' "$ci_version"
  exit "$code"
fi

if ! command -v "$GITLEAKS" >/dev/null 2>&1 && [ ! -x "$GITLEAKS" ]; then
  printf 'Gitleaks introuvable (%s). Utiliser --versions-only hors CI.\n' "$GITLEAKS" >&2
  exit 1
fi

# La valeur est fabriquée à l'exécution et jamais écrite dans le dépôt : en dur, elle serait
# elle-même détectée par le scan d'historique, qui rougirait pour toujours. 64 caractères
# hexadécimaux dépassent le seuil d'entropie de la règle generic-api-key.
probe="api_key = \"$(openssl rand -hex 32)\""
if printf '%s\n' "$probe" | "$GITLEAKS" stdin --redact --no-banner >/dev/null 2>&1; then
  printf 'NON DÉTECTÉ : une valeur à haute entropie est passée au travers du scanner.\n' >&2
  code=1
fi

# Le pendant du test précédent : .env.example est versionné et ne porte que des valeurs
# manifestement factices. S'il venait à déclencher une règle, le job rougirait sur tout le dépôt
# et la cause serait cherchée ailleurs.
if ! "$GITLEAKS" stdin --redact --no-banner < .env.example >/dev/null 2>&1; then
  printf 'FAUX POSITIF : .env.example déclenche une règle du scanner.\n' >&2
  code=1
fi

if [ "$code" -eq 0 ]; then
  printf 'Gitleaks %s : détection vérifiée, .env.example silencieux, versions accordées.\n' \
    "$ci_version"
fi

exit "$code"
