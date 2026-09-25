# boutique

Boutique en ligne, chart complet

Projet genere par **forge** a partir de `forge.yml`. Toute modification
structurelle passe par ce fichier : editez-le puis relancez
`forge generate`, ou recuperez les evolutions de gabarit avec
`forge update`.

## Identite

- **Service** : `boutique`
- **Responsable** : Equipe Plateforme
- **Environnements** : dev, prod

## Domaines generes

| Domaine | Repertoire | Role |
| --- | --- | --- |
| Helm | `helm/` | Complete Helm chart: commented values, templates and strict validation |

Chaque domaine est autonome : son `.copier-answers.yml` permet de le
mettre a jour seul (`forge update --only <domaine>`), et le supprimer
n'affecte pas les autres.

## Commandes utiles

```bash
forge generate          # regenere tous les domaines depuis forge.yml
forge validate          # validateurs de chaque domaine + coherence
forge diff              # ecart entre la cible et un rendu neuf
forge update            # applique les evolutions de gabarit
```
