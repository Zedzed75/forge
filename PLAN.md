# PLAN — forge

Memoire entre sessions. Une phase par session : lire ce fichier, traiter UNE phase,
mettre a jour la section « Etat courant », committer, s'arreter.

## Phases

- [x] **Phase 0 — Amorçage** : depot git, `_legacy/ansible-forge/`, `_legacy/helm-forge/`,
      `CLAUDE.md`, `PLAN.md`.
- [x] **Phase 1 — Audit et conception** (aucun code de production)
  - [x] Audit selectif de `_legacy/` -> `MIGRATION.md` (keep / adapt / discard par artefact,
        maturite de chaque outil, delimiteurs Jinja2, conflits avec copier).
  - [x] Conception -> `DESIGN.md` : hookspec pluggy, schema `forge.yml`, arborescence generee,
        invocation copier par plugin, surface CLI, questions ouvertes.
  - [x] **Validation humaine obtenue (2026-08-23)** : Q1 `[[ ]]` partout, Q5 aucun
        spec legacy externe (helper de test seulement), Q6 coeur minimal + reste par
        domaine, Q7 installation d'ansible-core/ansible-lint dans WSL a ma charge.
        Q2, Q3, Q4, Q8 retenues comme recommandees, sans objection.
        Releve complet : `DESIGN.md` §8.
- [ ] **Phase 2 — Coeur**
  - [ ] Scaffolding uv : `pyproject.toml`, `src/forge/`, `src/forge/plugins/`, `tests/`.
  - [ ] Chargement/validation du spec assemble a partir des sous-modeles de plugins.
  - [ ] Gestionnaire pluggy + hookspec validee.
  - [ ] Wrapper copier (run_copy / run_update).
  - [ ] Runner de validateurs (subprocess, erreurs claires, outil absent gere proprement).
  - [ ] Verbes CLI cables de bout en bout avec un plugin `demo` interne (tests seulement).
  - [ ] Harnais de tests golden (`tests/specs/` -> `tests/golden/`, commande de re-benediction).
  - [ ] Tests unitaires : assemblage du spec, enregistrement des plugins.
- [ ] **Phase 3 — Portage du plugin Ansible**
  - [ ] `pipx install ansible-core ansible-lint` dans WSL Debian (decision Q7).
  - [ ] Instantane de parite : generation legacy -> `tests/parity/ansible/`.
  - [ ] Portage gabarits / sous-modele de spec / validateurs / tests selon MIGRATION.md.
  - [ ] Catalogue de roles complet : common, users, ssh_hardening, firewall, nginx, docker,
        postgresql (portage d'abord, puis roles manquants un par un).
  - [ ] Spec golden + benediction des references une fois la parite atteinte.
  - [ ] MIGRATION.md et PLAN.md mis a jour, commit.
- [ ] **Phase 4 — Portage du plugin Helm**
  - [ ] Instantane de parite si l'outil legacy sait generer.
  - [ ] Portage gabarits (delimiteurs -> `[[ ]]`), sous-modele, validateurs, tests.
  - [ ] Catalogue de composants : deployment+service, ingress, configmap, statefulset,
        cronjob, secret (placeholders), hpa, pdb, serviceaccount+RBAC, networkpolicy.
  - [ ] Revue d'interface : points ou le hookspec/coeur a du plier ; refactor du contrat
        **avec validation humaine** avant tout 3e plugin.
- [ ] **Phase 5 — Valeur inter-domaines**
  - [ ] Verifications de coherence (namespaces Helm vs envs, groupes Ansible vs hosts,
        nom/labels de service identiques partout) avec messages actionnables.
  - [ ] `forge update` (copier update par domaine, `--only`) et `forge diff`.
  - [ ] Tests des deux, dont une mise a jour apres modification deliberee d'un gabarit.
- [ ] **Phase 6 — Finition**
  - [ ] Revue critique : code mort, duplication, cas d'erreur.
  - [ ] README (architecture, guide d'ecriture de plugin, exemples) + section migration.
  - [ ] `examples/` : un spec commite et sa sortie deux domaines.
  - [ ] Suppression de `_legacy/`.
  - [ ] Recapitulatif des changements, commit final.

## Etat courant / prochaine action

**Etat** : phases 0 et 1 terminees et **validees** (2026-08-23). Aucun code de
production ecrit, conformement a la consigne de la phase 1. Les huit questions
ouvertes sont tranchees : voir le releve de decisions dans `DESIGN.md` §8.

Verifie experimentalement pendant la phase 1 (spike copier 9.17.2, cf.
`MIGRATION.md` §2) : balise `yield` imbriquee, extensions Jinja personnalisees,
`copier update` sur gabarit interne au depot, delimiteurs `[[ ]]`, contournement
des chemins longs sous Windows.

**Prochaine action** : demarrer la **phase 2 — Coeur** dans une session neuve.
Points d'entree : `DESIGN.md` §2 (hookspec), §5 (invocation copier), §7 (CLI) et
§9 (arborescence du depot) ; `MIGRATION.md` §2 (contraintes copier verifiees) et
§5 (doublons a fusionner dans le coeur).

Rappels pour la phase 2 :
- `uv` n'est installe ni sous Windows ni dans WSL : l'installer avant le scaffolding.
- Le depot forge est configure avec `core.longpaths=true` et `.gitattributes`
  (`eol=lf`) ; ne pas les retirer, les tests golden en dependent.
- Le plugin `demo` de la phase 2 doit exercer la balise `yield` imbriquee et une
  extension Jinja, sinon la phase 3 decouvrira les problemes trop tard.

## Journal des sessions

- Session 1 (2026-08-23) : phase 0 (amorçage) puis phase 1 (audit + conception).
