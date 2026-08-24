# tests/parity — instantanés de parité

Sortie **figée** des générateurs d'origine, produite avant leur portage. C'est
la référence de comparaison des phases 3 et 4 : le plugin porté doit reproduire
ce contenu, aux écarts volontaires près, tous inscrits dans `MIGRATION.md` §7.

`_legacy/` est supprimé en phase 6 ; ces instantanés, eux, restent versionnés :
ils sont la seule trace vérifiable de ce que faisait l'outil d'origine.

| Domaine | Instantané | Cas | Fichiers | Producteur |
| --- | --- | --- | --- | --- |
| Ansible | `ansible/` | 6 | 319 | `snapshot_ansible.py` |

## Ansible

Les six cas sont les cinq spécifications de test d'`ansible-forge`
(`minimal`, `web_stack`, `multi_env`, `hardened`, `full_stack`) et son exemple
livré (`exemple`). Régénération, tant que `_legacy/` existe :

```bash
PYTHONPATH=_legacy/ansible-forge/src .venv/Scripts/python.exe tests/parity/snapshot_ansible.py
```

Les fins de ligne sont normalisées en LF à l'écriture : la comparaison porte sur
le contenu, jamais sur la plateforme qui a produit l'instantané.
