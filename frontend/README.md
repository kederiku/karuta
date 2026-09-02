# Application publique

Front public de Karuta : landing page et comparateur de prix, multilingue et
multi-tenant par licence. L'application Next.js elle-même n'est pas encore
initialisée ; ce document décrit les conventions que tout code déposé ici devra
respecter, et l'outillage qui les vérifie.

## Outillage

Tout passe par les configurations partagées du workspace, jamais par une
configuration locale :

| Outil      | Source                      | Commande         |
| :--------- | :-------------------------- | :--------------- |
| TypeScript | `@karuta/config-typescript` | `pnpm typecheck` |
| ESLint     | `@karuta/config-eslint`     | `pnpm lint`      |
| Prettier   | `.prettierrc.json` (racine) | `pnpm format`    |

`pnpm lint` et `pnpm format` s'exécutent depuis la racine et traversent tout le
dépôt : il n'y a qu'une configuration de lint pour l'ensemble du monorepo.
`pnpm lint:fix` corrige ce qui est corrigeable — c'est aussi ce qu'appelle le
hook pre-commit sur les fichiers `.ts` et `.tsx`.

## Conventions de nommage

- `PascalCase.tsx` pour les composants React.
- `camelCase.ts` pour tout le reste — hooks, utilitaires, types, tests.

## Conventions vérifiées par ESLint

- `any` est interdit : utiliser `unknown` et réduire le type.
- Ordre des imports : externes, puis `@/packages`, puis `@/features`, puis
  relatifs, avec une ligne vide entre les groupes.
- `React.FC` est interdit : écrire une fonction nommée dont les props sont typées
  explicitement.
- Accessibilité : HTML sémantique avant ARIA, `alt` obligatoire sur les images,
  contrôles atteignables au clavier.
- `@ts-ignore` est interdit ; `@ts-expect-error` est accepté s'il porte une
  description. Toute désactivation de règle doit être justifiée sur place.

## Conventions non outillées

Elles ne sont vérifiées qu'en revue tant que le code applicatif n'existe pas :

- Composants serveur par défaut. `'use client'` seulement quand l'état, les
  effets ou les écouteurs l'imposent, et le plus bas possible dans l'arbre.
- Pas de `useEffect` pour récupérer des données : c'est le rôle de TanStack Query.
- Pas de logique métier dans les composants : elle va dans un hook ou dans `lib/`.
- Types dérivés de l'API : importer depuis `src/generated/`, ne jamais redéfinir
  un type déjà généré.
- Aucune valeur en dur : couleurs via les tokens, textes via l'i18n, URL via des
  constantes.

Ces règles viennent du document 10 « Conventions de développement & Definition of
Done », §3.
