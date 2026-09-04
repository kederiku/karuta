// Transcription exécutable du format de message fixé par le doc 10 §1. Le document fait foi :
// une divergence se corrige ici, jamais dans le doc, et les listes ci-dessous ne s'élargissent
// pas d'elles-mêmes (doc 10 §10) — tout besoin passe par le modèle de blocage du doc 19 §9.
//
// .mjs et non .js : le package.json racine ne déclare pas "type": "module", un
// commitlint.config.js serait donc chargé en CommonJS et « export default » échouerait. Même
// convention que eslint.config.mjs.
export default {
  // config-conventional apporte les règles de forme — casse, point final, longueurs, lignes
  // blanches. Aucune n'est redéclarée : ce qui n'est pas ci-dessous est hérité délibérément.
  extends: ["@commitlint/config-conventional"],

  // La valeur par défaut renvoie au site Conventional Commits, qui décrit onze types et aucun
  // scope : elle décrirait autre chose que ce que cette configuration applique.
  helpUrl: "https://app.notion.com/p/3cffd4282b908192973de15086bf7e0a",

  rules: {
    // Sept types au lieu des onze de config-conventional. Ordre du doc 10 §1 et non
    // alphabétique, pour que le message d'erreur se relise ligne à ligne contre le document.
    // Les révisions produites par « git revert » gardent leur message automatique, que
    // commitlint ignore : retirer le type revert ne les casse pas.
    "type-enum": [2, "always", ["feat", "fix", "refactor", "docs", "test", "chore", "perf"]],

    // Huit scopes (décision E23) : adr a été retiré, une décision d'architecture se cite en
    // pied — Refs ADR-00NN — et non en scope. config-conventional n'en déclare aucun, donc
    // cette règle est la seule à faire échouer docs(adr).
    "scope-enum": [
      2,
      "always",
      ["api", "scraping", "frontend", "backoffice", "ui", "db", "infra", "docs"],
    ],

    // Le doc 10 §1 écrit <type>(<scope>) sans crochets là où le corps et le pied sont
    // crochetés : le scope est obligatoire. scope-enum ne suffit pas — il rend la main sans
    // rien vérifier quand le scope est absent.
    "scope-empty": [2, "never"],

    // subject-case est hérité tel quel, et non remplacé par un lower-case strict : la règle
    // héritée interdit la majuscule initiale sans interdire Orval, FastAPI ou README en
    // milieu de description. L'impératif, lui, n'est pas automatisable et reste à la revue.
  },
};
