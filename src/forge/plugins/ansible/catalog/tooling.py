"""Versions des outils Ansible contre lesquelles forge valide ce qu'il génère.

Pendant, pour les **outils**, de ce que `collections.py` fait pour les
**collections** : une version est écrite ici et nulle part ailleurs dans le
domaine. La différence de traitement entre les deux est voulue, et vaut d'être
lue.

- Une **collection** est une dépendance du projet généré : elle est déclarée
  dans son `requirements.yml`, elle voyage avec lui, et deux endroits qui n'en
  diraient pas la même version décriraient deux projets différents. D'où
  l'intervalle unique de `collections.py`, publié aux autres domaines par la
  projection du plugin plutôt que recopié.
- Un **outil** est ce qu'une machine lance *sur* le projet. Le projet généré a
  sa propre CI, forge a la sienne, et le pipeline engendré à la racine du dépôt
  a la sienne : trois machines, trois provisionnements. Ce module dit contre
  quelles versions forge a réellement validé sa sortie ; un test interdit aux
  trois de diverger en silence.

**ansible-core reste en 2.19** : c'est la dernière branche qui accepte Python
3.11 comme nœud de contrôle, et 3.11 est dans la matrice de la CI de forge
comme dans le `setup-python` du workflow généré. Passer en 2.20 ou 2.21 demande
d'abord de retirer 3.11 des deux.

Procédure de montée, identique à celle des collections : changer le numéro ici,
lancer la CI, corriger les gabarits si le validateur a durci une règle, et
livrer la montée dans son propre commit — jamais en passager d'un autre.
"""

from __future__ import annotations

#: Interpréteur Ansible. Voir le paragraphe sur la branche 2.19 ci-dessus.
ANSIBLE_CORE = "2.19.13"

#: Vérificateur de bonnes pratiques. Une version qui durcit une règle fait
#: passer au rouge un projet généré dont pas une ligne n'a bougé : c'est
#: exactement ce que l'épinglage évite.
ANSIBLE_LINT = "26.9.0"

#: Version de Python posée par le workflow du projet généré. Liée à
#: `ANSIBLE_CORE` : elle est ici pour qu'on ne puisse pas monter l'un en
#: oubliant l'autre.
PYTHON_VERSION = "3.11"


def pip_requirements() -> tuple[str, ...]:
    """Les deux outils au format attendu par `pip install`, dans l'ordre d'usage.

    Exemple : ``("ansible-core==2.19.13", "ansible-lint==26.9.0")``. La version
    est toujours exacte — un intervalle rendrait au dépôt PyPI le dernier mot
    sur ce que la CI du projet généré exécute.
    """
    return (f"ansible-core=={ANSIBLE_CORE}", f"ansible-lint=={ANSIBLE_LINT}")


def context() -> dict[str, str]:
    """Ce que les gabarits du domaine lisent sous `domain.tooling`."""
    return {
        "ansible_core": ANSIBLE_CORE,
        "ansible_lint": ANSIBLE_LINT,
        "python_version": PYTHON_VERSION,
        "pip_install": " ".join(f'"{besoin}"' for besoin in pip_requirements()),
    }
