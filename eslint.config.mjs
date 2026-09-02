// Configuration unique du dépôt : `eslint .` depuis la racine couvre les deux apps,
// les paquets partagés et les fichiers hors workspaces, que `pnpm -r` n'atteint pas.
// Les règles vivent dans @karuta/config-eslint ; ne rien ajouter ici.
export { default } from "@karuta/config-eslint";
