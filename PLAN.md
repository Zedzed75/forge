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
  - [x] **Validation humaine obtenue** (2026-08-23) — Q1 A, Q2 B, Q3 A, Q4 A, Q5 B, Q6 A, Q7 A.
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

**Etat** : phases 0 et 1 terminees et **validees par l'humain** (2026-08-23).
Decisions arretees : voir `DESIGN.md` § « Questions ouvertes » (reponses inscrites).

**Prochaine action** : demarrer la **phase 2 — Coeur**.
Point d'entree : `DESIGN.md` (hookspec, schema `forge.yml`, invocation copier, CLI)
et `MIGRATION.md` (ce qui sera porte en phases 3-4).

## Journal des sessions

- Session 1 (2026-08-23) : phase 0 (amorçage) + phase 1 (audit + conception).
  Livrables : `CLAUDE.md`, `PLAN.md`, `MIGRATION.md`, `DESIGN.md`. Puis validation
  humaine des 7 questions ouvertes -> decisions inscrites dans `DESIGN.md`.
