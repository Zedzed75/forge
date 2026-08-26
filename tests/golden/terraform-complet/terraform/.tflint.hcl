# =============================================================================
# .tflint.hcl — règles appliquées par tflint
# =============================================================================
# Fichier généré par forge.
#
# tflint voit ce que « terraform validate » laisse passer : une contrainte de
# version de provider absente, une variable déclarée et jamais employée, un
# nom de ressource hors convention. Les deux outils sont complémentaires, aucun
# ne remplace l'autre.
#
# Le jeu de règles « terraform » est intégré à tflint : aucun « tflint --init »
# n'est nécessaire, et la validation fonctionne sans accès réseau.
# =============================================================================

config {
  # Les modules locaux sont inspectés, pas ceux du registre : inspecter les
  # seconds demanderait de les télécharger, donc un accès réseau, pour
  # signaler des défauts qui ne sont pas les nôtres.
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
