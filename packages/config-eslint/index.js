import comments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import prettierConfig from "eslint-config-prettier/flat";
import importPlugin from "eslint-plugin-import";
import jsdoc from "eslint-plugin-jsdoc";
import jsxA11y from "eslint-plugin-jsx-a11y";
import tseslint from "typescript-eslint";

const IGNORED = [
  "**/node_modules/**",
  "**/.next/**",
  "**/dist/**",
  "**/coverage/**",
  // Client d'API produit par Orval et versionné (ADR-0024) : il est réécrit à chaque
  // régénération, une correction apportée ici ne survivrait pas.
  "**/src/generated/**",
];

export default tseslint.config(
  { ignores: IGNORED },

  // `recommended` et non `strict` : `strict` active no-non-null-assertion, qui
  // mettrait en faute la lecture d'environnement prescrite par le doc 07 §2.2.
  // `recommended` porte déjà no-explicit-any en erreur, exigé par le doc 10 §3.
  ...tseslint.configs.recommended,

  // Les 31 règles de ce préréglage sont déjà en erreur : c'est le « mode erreur »
  // qu'exige le doc 10 §3. Ne pas y ajouter les règles que le plugin laisse
  // délibérément désactivées, dont une est dépréciée.
  jsxA11y.flatConfigs.recommended,

  jsdoc.configs["flat/recommended-typescript"],
  comments.recommended,

  {
    files: ["**/*.{ts,tsx}"],
    plugins: { import: importPlugin },
    rules: {
      "import/order": [
        "error",
        {
          groups: ["builtin", "external", "internal", "parent", "sibling", "index"],
          // Ordre du doc 10 §3 : externes → @/packages → @/features → relatifs.
          // Les paquets du workspace précèdent les modules internes de l'app.
          pathGroups: [
            { pattern: "@karuta/**", group: "internal", position: "before" },
            { pattern: "@/features/**", group: "internal", position: "after" },
          ],
          pathGroupsExcludedImportTypes: ["builtin"],
          "newlines-between": "always",
        },
      ],

      "@typescript-eslint/no-restricted-types": [
        "error",
        {
          types: {
            "React.FC": "Composants : fonctions nommées et props typées explicitement (doc 10 §3).",
          },
        },
      ],

      // Sévérité fixée par le doc 20 §22 : un avertissement, pas une erreur.
      // N'ajouter --max-warnings 0 à aucun script, cela la rendrait bloquante.
      "jsdoc/require-jsdoc": ["warn", { publicOnly: true }],
      "jsdoc/no-types": "error",
      "@eslint-community/eslint-comments/require-description": "error",
      "@typescript-eslint/ban-ts-comment": [
        "error",
        { "ts-expect-error": "allow-with-description", "ts-ignore": true },
      ],
    },
  },

  // Aucune règle de nommage n'est activée nulle part au-dessus : le JSON de l'API
  // reste en snake_case de bout en bout, et les types générés avec lui (doc 03 §8).

  // En dernier : neutralise les règles de mise en forme qu'ESLint reprendrait à
  // Prettier. Toute configuration ajoutée après celle-ci les réactiverait.
  prettierConfig,
);
