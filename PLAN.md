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
- [x] **Phase 2 — Coeur** (2026-08-23)
  - [x] Scaffolding uv : `pyproject.toml`, `src/forge/`, `src/forge/plugins/`, `tests/`.
  - [x] Chargement/validation du spec assemble a partir des sous-modeles de plugins.
  - [x] Gestionnaire pluggy + hookspec validee.
  - [x] Wrapper copier (run_copy / run_update) + `copier.yml` racine unique.
  - [x] Runner de validateurs (subprocess, erreurs claires, outil absent gere proprement).
  - [x] Verbes CLI cables de bout en bout avec un plugin `demo` interne (tests seulement).
  - [x] Harnais de tests golden (`tests/specs/` -> `tests/golden/`, `pytest --regen-golden`).
  - [x] Tests unitaires : assemblage du spec, enregistrement des plugins.
  - [x] Bonus : controles inter-domaines, `forge diff`, pont WSL, CI GitHub du coeur.
- [x] **Phase 3 — Portage du plugin Ansible** (2026-08-25)
  - [x] ansible-core 2.21.3 + ansible-lint 26.8.0 dans WSL Debian (decision Q7),
        sous `/opt/forge-venv`, avec les collections Galaxy sous `/opt/forge-collections`.
  - [x] Instantane de parite : 319 fichiers, 6 cas -> `tests/parity/ansible/`.
  - [x] Portage gabarits / sous-modele de spec / validateurs / tests selon MIGRATION.md.
  - [x] Catalogue de roles complet : les 7 roles portes, donnees identiques au legacy.
  - [x] Spec golden (`ansible-ci.yml`) couvrant `write_ci`, que la parite ne couvrait pas.
  - [x] MIGRATION.md et PLAN.md mis a jour, commit.
- [x] **Phase 4 — Portage du plugin Helm** (2026-08-25)
  - [x] Instantane de parite : 32 fichiers, 2 cas -> `tests/parity/helm/`.
  - [x] Portage gabarits, sous-modele, validateurs, entretien, tests.
  - [x] Catalogue de composants **complet** : les 13 familles, dont les 9 creees
        (ingress, configmap, statefulset, cronjob, secret, hpa, pdb,
        serviceaccount+RBAC, networkpolicy).
  - [x] **Revue d'interface : arbitree (2026-08-25).** R2 -> nouveau hook
        `forge_check_spec`, appele avant tout rendu ; R3 -> `tree.py` reste au
        plugin, tenu a jour par un test obligatoire dans chaque domaine.
        R1, R4, R5, R6, R7 enterines et documentes.
- [x] **Phase 5 — Valeur inter-domaines** (2026-08-25)
  - [x] Verifications de coherence, avec messages actionnables. **Un faux positif
        corrige** : les deux domaines declaraient une facette `hosts` qui ne
        designait pas la meme chose, et `forge validate` echouait sur une
        specification parfaitement coherente.
  - [x] **Vocabulaire partage des facettes** (`FACET_VOCABULARY`) : le nom d'une
        facette est un espace de noms commun a tous les plugins.
  - [x] `Projection.environments` porte desormais ce que le domaine **materialise**,
        et non une recopie de `service.environments` : un environnement deploye
        par un domaine et ignore par l'autre devient visible.
  - [x] `forge update --only` et `forge diff` par domaine, testes sur deux domaines.
  - [x] Specification `deux-domaines.yml` + golden, et test d'integration lancant
        les **neuf** validateurs reels des deux chaines d'outils.
- [x] **Phase 6 — Le choix des domaines, rendu explicite** (2026-08-25)
  - [x] `CLAUDE.md` porte l'arborescence cible **complete** du brief (cinq
        plugins) et la regle « les domaines sont un choix, jamais un lot ».
  - [x] README : section dediee aux trois facons de choisir.
  - [x] CLI : `forge generate` annonce ce qu'il va produire avant d'ecrire ;
        message actionnable quand aucun domaine n'est demande ; `forge plugins`
        distingue les domaines demandes par la specification des autres.
  - [x] `tests/test_domain_selection.py` : 11 tests verrouillant les trois
        facons de choisir, dont un entretien ne retenant qu'un domaine.
- [x] **Phase 7 — Plugin Terraform** (premier domaine ecrit de zero) (2026-08-26)
  - [x] Aucun code legacy a porter. Promesse tenue : **une seule ligne du coeur
        a change**, l'entree de `BUILTIN_PLUGINS`. Le reste est dans
        `plugins/terraform/`, plus quatre attentes de test qui comptaient les
        domaines.
  - [x] Catalogue de **sept familles** (`namespace`, `quota`, `registry_secret`,
        `service_account`, `network_policy`, `random_secret`, `tls_certificate`)
        et de leurs pieges mesures ; sous-modele `terraform:` ; 24 gabarits ;
        entretien.
  - [x] Validateurs : `terraform fmt -check`, `terraform init -backend=false`,
        `terraform validate` par environnement, `tflint --recursive`.
  - [x] Golden (`terraform-complet`) + test d'integration lancant les **huit**
        commandes reelles. 48 tests ajoutes.
  - [x] CI : les validateurs des domaines Helm **et** Terraform y sont installes.
        Helm n'y avait jamais ete ajoute (manque de la phase 4) : ses tests
        d'integration s'y ignoraient en silence.
- [x] **Phase 8 — Plugin pipeline** (CI/CD) — *mise de cote, puis terminee*
  - [x] Commencee, puis parquee sur `phase-8-pipeline` le 2026-08-26 pour
        consolider d'abord les domaines de production. Reprise ensuite, rebasee
        sur `master`, testee et terminee.
  - [x] Le domaine qui federe les autres **sans les connaitre** : il engendre un
        job de validation par domaine declare, avec les commandes que chacun
        annonce lui-meme. Le coeur assemble un `GenerationContext` a partir de
        hooks existants et n'en tire aucune conclusion.
  - [x] Deux dialectes — GitHub Actions et GitLab CI — pour les memes jobs.
  - [x] Validateurs : `actionlint` (GitHub), `yamllint` (GitLab). La
        dissymetrie est assumee et documentee : il n'existe pas de linter
        GitLab hors ligne.
  - [x] Golden sur les deux dialectes, 36 tests, dont le temoin decisif — un
        **domaine factice que le plugin n'a jamais vu** obtient son job.
  - [ ] Le domaine qui federe les autres : build d'image, appel des validateurs
        de chaque domaine present, deploiement par environnement.
  - [ ] Doit lire ce que les autres domaines declarent **sans les connaitre** :
        c'est le premier plugin dont la sortie depend des autres sections. A
        cadrer avec soin — le coeur ne doit pas devenir un ordonnanceur.
  - [ ] Validateurs : `actionlint` (GitHub) ou le linter GitLab.
- [x] **Phase 9 — Plugin monitoring** (2026-08-26)
  - [x] Six familles de regles (`availability`, `error_rate`, `latency`,
        `saturation`, `restarts`, `probe`), huit alertes, une configuration de
        collecte **par environnement** — les seuils et le namespace observe
        different d'un environnement a l'autre.
  - [x] Validateurs : `promtool check config`, `check rules`, et surtout
        **`promtool test rules`** : chaque alerte est livree avec un test
        unitaire qui prouve qu'elle se declenche, avec les bons libelles et les
        bonnes annotations. Trois commandes par environnement.
  - [x] Domaine **autonome** : il ne lit aucune autre section. Sa rencontre avec
        les autres domaines passe par les facettes (`namespaces`,
        `ingress_hosts`), comme prevu depuis la phase 5.
  - [x] Golden + test d'integration lancant promtool. 66 tests ajoutes.
- [x] **Phase 10 — Finition** (2026-08-26)
  - [x] Revue critique. Six elements de code mort supprimes apres verification
        qu'aucun chemin ne les atteignait, dont deux classes d'erreur jamais
        levees (`ToolMissingError`, `ValidationFailed`) : le coeur signale un
        outil absent par un **rapport**, pas par une exception, et lever aurait
        fait perdre le rapport.
  - [x] Duplication : le controle « environnement inconnu » etait reecrit a
        l'identique dans quatre domaines. Il vit desormais dans
        `plugins_api/checks.py`, qui ne parle que de `service.environments` —
        donc sans ajouter la moindre connaissance de domaine au coeur.
  - [x] README complet : architecture, guide d'ecriture de plugin (les dix
        hooks, la marche a suivre, les trois pieges qui ont mordu), provenance.
  - [x] `examples/` : cinq specifications commitees, dont **quatre cas
        mono-domaine**, toutes generees par la suite de tests.
  - [x] Ecarts de parite 12 a 15 leves **d'un bloc**, instantane re-beni dans le
        meme commit. Deux mentions conservees et expliquees : ce sont des noms de
        fichiers deposes sur les machines gerees, les renommer laisserait
        l'ancien en place.
  - [x] Suppression de `_legacy/`, de `tests/parity/`, de ses deux modules de
        test et de son harnais.

## Etat courant / prochaine action

**Etat** : **projet livre, cible complete**. Les dix phases sont terminees.
**568 tests collectes**, tous verts, integration comprise.

Les **cinq** domaines du brief d'origine sont livres et valides par leurs outils
reels : **Ansible**, **Helm**, **Terraform**, **monitoring**, **pipeline**.
Chacun se genere seul, et c'est le cas d'usage normal.

La promesse du projet : **une seule description du service, et vous choisissez
ce que vous en tirez.** Un domaine absent de `forge.yml` n'est jamais genere ;
`--only` restreint une execution ; l'entretien demande quels domaines produire.

Le cas a deux domaines (`tests/specs/deux-domaines.yml`) est **un** usage
possible, pas l'usage normal : il sert a prouver que deux domaines restent
coherents entre eux quand on les demande ensemble. Les **neuf** validateurs
externes des deux chaines d'outils y passent (`ansible-playbook --syntax-check`
par environnement, `ansible-lint`, `helm lint`, `helm template` et
`kubeconform -strict` par environnement), sans que le coeur sache ce qu'est un
role ou un chart.

Les deux domaines sont livres et enregistres (`BUILTIN_PLUGINS`) : `forge new`,
`forge generate`, `forge validate`, `forge diff` et `forge catalog <domaine>`
fonctionnent de bout en bout sur un vrai projet Ansible **et** sur un vrai chart
Helm.

Helm : **parite 32/32** avec le generateur d'origine, **plus neuf familles de
ressources creees** que le legacy n'avait jamais eues. Le chart complet passe
`helm lint`, `helm template` sur chaque environnement et `kubeconform -strict`.
Cinq defauts ont ete trouves par la complementation elle-meme et corriges
(cf. `MIGRATION.md` §7) — dont un StatefulSet prive de son Service headless,
qu'aucun validateur ne pouvait voir.

Ansible : **parite 313/313** sur les 6 cas de l'instantane, aux ecarts
documentes pres (`MIGRATION.md` §7). Et au-dela de la parite, le projet genere passe
`ansible-playbook --syntax-check` sur chaque environnement **et** `ansible-lint`
en profil `production` — ce que la suite legacy n'avait jamais verifie, son
unique test ignore portant precisement la-dessus.

Ce que la phase 2 avait livre :
- `copier.yml` racine unique, delimiteurs `[[ ]]`, cinq questions declarees.
- `src/forge/` : `spec/` (io, service, types, names, assembly), `plugins_api/`
  (hookspecs, manager, types), `render/` (copier_runner, scaffold, diff),
  `validate/` (tools, wsl, runner, consistency), `interview/`, `jinja_ext.py`,
  `pipeline.py`, `cli.py`.
- Plugin `demo` (`src/forge/plugins/demo/`), **jamais enregistre en production** :
  il est charge par `FORGE_PLUGINS=forge.plugins.demo.plugin` et exerce les
  yields imbriques, le filtrage de fichier par `[% if %]`, les filtres de plugin.
- Verbes CLI : `new`, `generate`, `validate`, `update`, `diff`, `plugins`,
  `catalog`, `--version`.
- `tests/` : specs de reference, golden benis, harnais `--regen-golden`.
- CI GitHub (matrice 3.11/3.12/3.13) ; les outils de domaine s'y ajoutent en
  phases 3 et 4.

Revue adversariale du coeur (2026-08-23) : 25 defauts reels confirmes, tous
corriges dans la foulee. Les cinq qui comptent pour la suite :
1. **Normalisation de sortie** — le `rstrip` par ligne et l'ecrasement des
   lignes vides herites du legacy **corrompaient** les scalaires YAML generes.
   Le coeur se limite desormais a `CRLF -> LF` + un saut final
   (`MIGRATION.md` §5, encadre). En phases 3 et 4, un gabarit qui laisse des
   blancs se corrige **dans le gabarit**, jamais dans le coeur.
2. **Noms de domaine** — un plugin nomme `service` ecrasait silencieusement le
   bloc partage du modele assemble. `register()` valide maintenant le nom
   (identifiant minuscule, ni mot-cle, ni nom reserve du modele racine).
3. **`_src_path`** — la reecriture salissait la cible et rendait `forge update`
   impossible ; forge corrige la ligne puis **s'arrete** en demandant le commit.
4. **Chainage `stdin_from`** — un libelle source inexistant produisait un
   « saute » vert ; c'est desormais une `PluginError`. Important pour Helm :
   `kubeconform` lit le rendu de `helm template` par stdin.
5. **Fichiers de niveau depot** — ecrits apres le rendu, jamais ecrases sans
   `--force`, `forge.yml` de la cible preserve avec ses commentaires, index
   calcule sur la specification et non sur `--only`, et compares par
   `forge diff` sous la rubrique `(racine)`.

Ecarts assumes par rapport a `DESIGN.md` §9 (arborescence prevue) :
- ajout de `pipeline.py` (enchainement des operations) pour que `cli.py` ne
  porte aucune logique ; ajout de `interview/service_flow.py`,
  `render/scaffold.py` et `render/diff.py` (SRP, limite de 600 lignes).
- `BUILTIN_PLUGINS` contient `forge.plugins.ansible.plugin` depuis la phase 3.
  Ajouter Helm en phase 4 = une ligne de plus, aucune autre modification du coeur :
  c'est la promesse de DESIGN.md §2.4, tenue.

## Revue d'interface — releve pour arbitrage humain

`PLAN.md` reservait cette revue a une validation humaine, avant tout 3e plugin.
**Arbitrage rendu le 2026-08-25** : R2 et R3 tranches comme recommande, les cinq
autres constats enterines. Le tableau reste ici comme releve de decisions — ne
pas le rouvrir sans raison nouvelle.

| # | Constat | Recommandation |
|---|---|---|
| R1 | **`Command.env` a ete ajoute en cours de route** (phase 3). `DESIGN.md` §2.1 decrivait `Command` sans ce champ. Sans lui, `ANSIBLE_COLLECTIONS_PATH` etait intransmissible et `--syntax-check` echouait sur des modules que `requirements.yml` declare pourtant ; Helm s'en sert pour `KUBECONFORM_SCHEMA_LOCATION`. | **Entériner** : deux domaines sur deux en ont eu besoin. Mettre `DESIGN.md` §2.1 a jour. |
| R2 | **ARBITRE : hook ajoute.** **Le contrat n'avait pas de controle croise au niveau du modele.** Un sous-modele de plugin ne voit que sa section : ni Ansible ni Helm ne peut verifier seul que les environnements qu'il cite existent dans `service.environments`. Les deux passent par `forge_consistency`, qui n'est appele qu'a `forge validate` — **pas a `forge generate`**. Une specification incoherente est donc generee sans broncher, et l'erreur ne sort qu'au `validate` suivant. | **Ajouter un hook** `forge_check_spec(spec) -> list[Issue]`, appele par le coeur juste apres l'assemblage du modele, donc avant tout rendu. `forge_consistency` resterait pour ce qui a besoin des fichiers ecrits. |
| R3 | **ARBITRE : laisse au plugin, avec test obligatoire.** **La liste des fichiers a ecrire est dupliquee dans chaque plugin** (`ansible/tree.py`, `helm/tree.py`). copier ne sait pas dire a l'avance ce qu'il va produire, et les deux domaines affichent une arborescence dans leur README. Un gabarit ajoute sans mise a jour de `tree.py` rend le README faux — un test l'attrape cote Ansible, la lecon a ete apprise deux fois. | **Service du coeur** : un rendu « a blanc » dans un tmpdir donne la liste exacte. Le coeur pourrait l'exposer aux gabarits (`domain.tree`) au lieu que chaque plugin la redevine. |
| R4 | **Les deux plugins ont invente le meme idiome, separement** : `domain.role_slots.<role>` et `domain.component_slots.<famille>`, un dict `{cle: [item] ou []}` qui permet a un gabarit propre a un element d'exister sans `[% if %]` dans le chemin. | **Documenter comme motif** dans `DESIGN.md` §5.3. Ne pas l'imposer dans le coeur : c'est une convention de gabarit, pas une API. |
| R5 | **`.copier-answers.yml` grossit.** Il porte l'integralite du dict `domain` : ~23 Ko sur le cas Ansible le plus riche. C'est voulu (decision Q3 : lisible, versionne, relu), mais personne n'avait chiffre. | **Laisser tel quel**, et le dire dans `DESIGN.md` §8 Q3. L'alternative — n'y mettre que la spec — casserait `copier update`. |
| R6 | **`DomainInfo.outdir` n'a jamais servi** : les deux domaines emploient le defaut (`ansible/`, `helm/`). | **Garder** : le champ coute une ligne et un domaine tiers en aura besoin (`terraform/environments/` par exemple). |
| R7 | **L'entretien demande deux fois son avis a l'utilisateur** : le coeur demande quels domaines generer, puis le plugin peut encore decliner en retournant `None`. Ansible s'en sert (aucun groupe nomme), Helm aussi (aucun composant). | **Garder**, mais le dire dans le hookspec : le `None` du plugin ne signifie pas « l'utilisateur refuse le domaine », il signifie « il n'y a rien a generer ». |

**CORRECTION DE CIBLE (2026-08-25).** Le brief d'origine nommait **cinq**
plugins — `ansible`, `helm`, `terraform`, `pipeline`, `monitoring` — et
`CLAUDE.md` les avait reduits a « Ansible, Helm, more later ». Les cinq phases
deja faites l'ont donc ete sur une cible amputee. `CLAUDE.md` porte desormais
l'arborescence cible complete ; le plan est etendu de trois phases de domaine.

Rien de ce qui a ete construit n'est remis en cause : le coeur est agnostique,
et les trois domaines restants sont precisement ce qui va le prouver — aucun ne
vient d'un outil legacy.

**Point de cadrage a corriger aussi** : les domaines sont un **choix**, jamais un
lot. Le mecanisme existe et fonctionne (section absente de forge.yml, `--only`,
entretien), mais la documentation et la CLI le mettent mal en avant.

**Consolidation du 2026-08-26** — recadrage demande par l'utilisateur : l'outil
doit pouvoir produire *a la demande* du Terraform, **ou** un chart Helm, **ou**
des roles Ansible. Chaque projet n'a pas besoin de tout, et le choix revient a
l'utilisateur. Le mecanisme existait ; ce qui manquait, c'est qu'il soit
**structurellement invulnerable a la derive** et **visible**.

Ce qui a ete fait :
- `tests/test_domain_selection.py` reecrit : **plus aucun nom ni nombre de
  domaine code en dur**. Tout est lu dans le registre de plugins, et
  `test_chaque_domaine_livre_a_une_specification_mono_domaine` fait echouer la
  suite si un domaine est ajoute sans son cas mono-domaine. 11 tests -> 34.
- Un cas mono-domaine parametre par domaine : generation, contenu reel de la
  cible, `forge validate`, `forge diff`, `forge plugins`. Terraform y entre, ce
  qui n'etait pas le cas.
- `examples/` livre : `ansible-only.yml`, `helm-only.yml`,
  `terraform-only.yml`, `foundation-and-chart.yml`, et un README qui explique les
  trois facons de choisir. **Chaque exemple est genere par la suite de tests** —
  un exemple perime est impossible.
- README recentre : « Un projet n'a pas besoin de tout », tableau des trois
  domaines et de leurs validateurs, en tete de fichier.

Un comportement a ete **decouvert** en ecrivant ces tests, et verrouille :
`--only` sur un domaine que la specification ne declare pas leve une erreur
nommee au lieu de ne rien produire. C'est le bon comportement — un silence
laisserait croire que le domaine a ete genere — mais il n'etait teste nulle part.

Ce que la phase 9 a etabli :
- **Un domaine peut se passer de connaitre les autres.** Le monitoring ne lit
  aucune section voisine : ce qu'il surveille est declare chez lui, et la
  coherence passe par les facettes. C'est le contre-exemple utile a la phase 8,
  ou le pipeline avait besoin d'un contexte fourni par le coeur.
- **`promtool test rules` verifie ce qu'aucun autre validateur du projet ne
  verifie : le sens.** Une regle d'alerte peut etre syntaxiquement irreprochable
  et rester muette pour toujours — metrique inexistante, libelle mal
  orthographie, comparaison du mauvais cote du seuil. Les tests unitaires
  d'alerte sont donc **inconditionnels** : les rendre facultatifs invitait au
  mauvais choix.
- **Les series de test doivent suivre les seuils.** promtool a trouve le defaut
  seul : un quantile de test a 1.9 s validait un seuil a 1 s et echouait sur un
  seuil a 2 s. Les fixtures sont desormais calculees a partir du seuil, avec une
  marge franche, et un test verifie cette propriete.
- **Un piege de Jinja est devenu une regle testee.** Une cle nommee `values`
  faisait ecrire `<built-in method values...>` dans un fichier genere : en
  Jinja, `objet.values` resout la methode du dict avant la cle. Deux garde-fous
  couvrent desormais **tous** les domaines — l'un sur la source des gabarits,
  l'autre sur la sortie rendue. Les gabarits Helm employaient deja la forme sure
  `c.config["keys"]` sans que ce soit ecrit nulle part.

Ce que la phase 10 a etabli :
- **La parite avait cesse de mesurer ce qui compte.** Elle comparait la sortie a
  des outils qui n'existent plus, alors que le projet genere les avait depasses
  des la phase 4 — neuf familles Helm inedites, `ansible-lint` en profil
  production. La retirer etait la seule facon de ne pas mentir sur ce que la
  suite verifie.
- **La revue de code mort a trouve une intention, pas seulement des lignes.**
  `ToolMissingError` et `ValidationFailed` decrivaient une conception qui n'a pas
  ete retenue : signaler par exception plutot que par rapport. Les garder aurait
  laisse croire qu'elles servaient.
- **Une duplication a quatre exemplaires est une specification implicite.** Le
  controle « environnement inconnu » etait identique partout parce qu'il ne
  releve d'aucun domaine : il porte sur `service.environments`, qui est du coeur.

Ce que la reprise de la phase 8 a etabli :
- **Les garde-fous de la phase 10 ont fait leur travail.** Rebaser la branche a
  fait echouer trois tests, et les trois avaient raison : un domaine livre sans
  sa specification mono-domaine, sans son exemple, et un decompte de domaines
  perime. Aucun n'aurait ete remarque sans eux.
- **Un temoin vaut mieux qu'une inspection.** La promesse « le pipeline ne
  connait aucun domaine » ne se prouve pas en relisant le code : elle se prouve
  avec un domaine factice que le plugin n'a jamais vu, et qui obtient son job.
- **Les trois defauts corriges avant la mise de cote portent chacun leur test.**
  Variables d'environnement du poste, ordre de deploiement, chainage stdin : ils
  ne peuvent plus revenir en silence.

**Prochaine action** : aucune. Le projet est livre, cible complete.

La phase 8 (pipeline) reste sur sa branche ; elle peut etre reprise apres. Le premier domaine dont
la sortie **depend des autres sections** de la specification. Le point a cadrer
n'est pas technique : c'est de lire ce que les autres domaines declarent sans
les connaitre, et sans que le coeur devienne un ordonnanceur.

Ce que la phase 7 a etabli, et qui sert a la phase 8 :
- **La promesse tient.** Ajouter un domaine a coute **une ligne** du coeur
  (`BUILTIN_PLUGINS`). Aucun hook n'a manque, aucun type n'a du etre elargi —
  contrairement a la phase 3, ou `Command.env` avait du etre ajoute en cours de
  route (constat R1).
- **Un validateur peut dicter une decision d'architecture.** `terraform fmt`
  aligne le `=` de lignes d'affectation consecutives ; un gabarit ne peut pas
  aligner des cles dont il ignore la longueur, la projection si. D'ou
  `plugins/terraform/hcl.py` et ses filtres exposes par la convention
  `<paquet>.jinja_ext` — premier domaine a avoir besoin de filtres pour autre
  chose que du YAML, et la convention a suffi.
- **Les validateurs reels trouvent encore ce que les tests ne voient pas.**
  `tflint` a signale `var.annotations` declaree et jamais employee des que la
  famille `namespace` n'etait pas retenue. Correction : les annotations sont
  apposees sur **toutes** les ressources — ce que leur description promettait
  deja. D'ou `test_toute_variable_declaree_est_employee_par_un_gabarit`, qui
  eprouve **chaque famille isolement** : le cas complet aurait masque le defaut.
- **La CI ne validait pas ce qu'elle croyait valider.** Ni `helm` ni
  `kubeconform` n'y avaient jamais ete installes : les tests `integration` s'y
  ignoraient, et une suite verte ne disait rien des projets generes. Les quatre
  validateurs manquants y sont desormais installes.
- **Le vocabulaire des facettes a son premier cas reel.** Terraform et Helm
  declarent tous deux `namespaces` : Terraform cree le cloisonnement, Helm y
  deploie. Un desaccord signifie que le chart vise un namespace que personne ne
  cree, et `forge validate` le dit sans qu'aucune regle « si terraform alors
  helm » n'existe dans le coeur.

Rappels pour la phase 8 :
- Poser le tag `v1.0.0` a la fin de la phase 10 (`v0.8.0` marque la phase 9).
  **Correction de numerotation** : le rappel de la phase 6 reservait `v1.0.0`
  a cette phase, a une epoque ou elle etait la derniere. La cible corrigee en
  compte dix : `v1.0.0` revient a la phase 10, et les phases 6 et 7 portent
  `v0.5.0` et `v0.6.0`.
- Le domaine `pipeline` ne doit connaitre **aucun** autre domaine par son nom.
  Ce qu'il peut lire : `manager.domain_names()`, les `DomainInfo` (dont
  `outdir`), les `Command` rendues par `forge_validators`, et les `Projection`.
  C'est deja tout ce qu'il faut pour engendrer un job par domaine present.
- `Command` porte deja `tool`, `argv`, `cwd`, `env` et `install_hint` : un job
  de CI se derive de cette liste sans que le plugin sache ce qu'est un chart.
  Le risque est ailleurs — l'**installation** de chaque outil, que `Command` ne
  decrit pas. A trancher en phase 8 : l'inferer d'une table propre au plugin
  pipeline, ou elargir le contrat.

**Ce que la phase 7 n'a PAS fait**, et qu'il ne faut pas croire acquis :
- le domaine Terraform ne pose que des objets **Kubernetes** (plus `random` et
  `tls`). Aucun provider de cloud : il faudrait des identifiants pour valider,
  et `forge validate` ne joint jamais aucune infrastructure ;
- `terraform plan` et `apply` ne sont **pas** des validateurs : ils demandent un
  cluster. Seuls `fmt`, `init -backend=false`, `validate` et `tflint` le sont.

Ce que la phase 5 a etabli :
- **Deux domaines qui se rencontrent revelent ce qu'un seul ne peut pas.** Le
  faux positif sur `hosts` etait invisible tant qu'un seul domaine existait, et
  DESIGN.md proposait litteralement les deux noms qui entraient en collision.
- Le **vocabulaire des facettes** est un espace de noms partage : l'ajouter a la
  documentation ne suffit pas, le coeur ne compare desormais que les facettes
  qui y figurent. Une facette hors vocabulaire est sans danger, mais sans effet.
- La comparaison de projections rend un constat qu'aucun domaine ne peut faire
  seul : « l'environnement 'prod' est materialise par helm mais pas par
  ansible ». C'est un avertissement, pas une erreur — un service uniquement
  conteneurise est legitime ; ce qui ne l'est pas, c'est que personne ne le dise.

Rappels pour la phase 6 :
- Poser le tag `v0.5.0` a la fin de la phase 6 (`v0.4.0` marque la phase 5).
  *(Ce rappel disait `v1.0.0` : corrige, cf. les rappels de la phase 8.)*
- Les ecarts de parite 12 a 15 (mentions periemees de `ansible-forge` et
  `helm-forge` dans les README generes) doivent etre leves **d'un bloc**, en
  re-benissant les instantanes dans le meme commit — c'est le bon moment,
  puisque `_legacy/` disparait et que la parite cesse alors de servir.
- `tests/specs/deux-domaines.yml` est le candidat naturel pour `examples/`. Points d'entree : `MIGRATION.md` §4 (classement par artefact) et
§7 (etat du portage Ansible, dont les ecarts a ne pas reproduire) ; `DESIGN.md`
§3 (section `helm:`) et §8 Q6.

Ce que les phases 3 et 4 ont etabli, et qui sert a la phase 5 :
- **Le patron de portage** : instantane de parite fige d'abord, conversion
  ensuite, boucle jusqu'a zero ecart. Il a tenu deux fois.
- **La parite ne se degrade pas quand on ajoute**, a condition d'ecrire les
  ajouts de facon inerte pour les cas figes. C'est ce qui a permis de creer neuf
  familles Helm sans perdre un seul des 32 fichiers de reference.
- **Les validateurs reels trouvent ce que les tests ne voient pas**, et
  reciproquement : ansible-lint a trouve 255 violations dans un fichier que la
  parite declarait parfait ; le test de rendu complet a trouve un StatefulSet
  prive de son Service, qu'aucun validateur ne pouvait voir.

Rappels pour la phase 5 :
- Poser le tag `v0.4.0` a la fin de la phase 5 (`v0.3.0` marque la phase 4).
- Les deux domaines declarent deja des facettes comparables : Ansible expose
  `hosts` et `groups`, Helm expose `hosts` et `namespaces`. La comparaison
  generique du coeur (`validate/consistency.py`) est ecrite mais n'a jamais eu
  deux domaines a comparer sur une meme specification : c'est le coeur de la
  phase 5.
- `forge update` et `forge diff` existent depuis la phase 2 et sont testes ; la
  phase 5 demande d'y ajouter le test d'une mise a jour **apres modification
  deliberee d'un gabarit** — le motif du depot de gabarit temporaire
  (`tests/test_cli_coverage.py::_depot_de_gabarit`) le permet deja.

## Journal des sessions

- Session 1 (2026-08-23) : phase 0 (amorçage) puis phase 1 (audit + conception).
- Session 2 (2026-08-23) : phase 2 (coeur complet, plugin `demo`, tests golden, CI),
  puis revue adversariale du coeur : 25 defauts confirmes et corriges, suite de
  tests portee de 129 a 179 cas.
- Session 3 (2026-08-25) : phase 3 (plugin Ansible porte a parite integrale,
  50 gabarits convertis, 7 roles, validateurs reels qui passent). 213 tests.
- Session 4 (2026-08-25) : phase 4 (plugin Helm porte a parite 32/32, puis neuf
  familles de ressources creees ; 5 defauts trouves par la complementation),
  puis revue d'interface arbitree : hook `forge_check_spec` ajoute, `tree.py`
  laisse au plugin sous test obligatoire. 245 tests.
- Session 5 (2026-08-25) : phase 5 (controles inter-domaines reellement
  exerces ; faux positif de facette corrige, vocabulaire partage introduit,
  specification a deux domaines et ses neuf validateurs reels). 260 tests.
  Puis **correction de cible** : le brief nommait cinq plugins, `CLAUDE.md` les
  avait reduits a deux. Plan etendu, cadrage du choix des domaines corrige
  (phase 6). 271 tests.
- Session 6 (2026-08-26) : phase 7 (plugin Terraform ecrit de zero — sept
  familles, 24 gabarits, huit validateurs reels qui passent). Un defaut trouve
  par tflint et corrige ; manque de la CI de la phase 4 comble. 319 tests.
  Puis phase 8 commencee (domaine pipeline) et **mise de cote sur la branche
  `phase-8-pipeline`** a la demande de l'utilisateur, pour consolider d'abord
  le choix des domaines : tests derives du registre, `examples/` livre,
  README recentre. 342 tests.
  Puis phase 9 (plugin monitoring : six familles, huit alertes, chacune livree
  avec le test unitaire qui prouve qu'elle se declenche). Deux defauts trouves
  par promtool et par le garde-fou generique. 531 tests.
  Puis phase 10 (finition) : revue critique, duplication a quatre exemplaires
  factorisee, ecarts de parite leves d'un bloc, `_legacy/` et la parite
  supprimes, README complet. 515 tests. Projet livre, `v1.0.0`.
  Puis reprise de la phase 8 : branche rebasee sur master, domaine pipeline
  termine et teste (deux dialectes, temoin par domaine factice, les trois
  defauts verrouilles). 568 tests. **Cible complete : les cinq domaines du
  brief sont livres.**
