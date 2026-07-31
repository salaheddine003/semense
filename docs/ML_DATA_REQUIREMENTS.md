# Données requises pour améliorer le modèle

Les fuites de données ont été supprimées du modèle. Les scores fiables ne
pourront pas atteindre durablement les objectifs demandés sans nouvelles
variables explicatives. Il est interdit de réintroduire `YD16QH`, `%MOIS` ou un
identifiant d'essai uniquement pour augmenter artificiellement les métriques.

## Données prioritaires

| Domaine | Variables minimales | Clé de jointure |
|---|---|---|
| Météo | pluie, températures min/max, rayonnement, vent, humidité | site + date |
| Sol | texture, pH, matière organique, réserve utile | parcelle |
| Conduite | semis, densité, irrigation, fertilisation, traitements | essai/parcelle |
| Phénologie | dates de levée, floraison, maturité | essai + matériel |
| Génétique | caractéristiques stables utilisables avant l'essai | matériel |

## Contrats qualité

- Couverture minimale de 90 % pour les variables retenues.
- Unités et fuseaux horaires normalisés.
- Valeurs agronomiques bornées avec quarantaine, pas suppression silencieuse.
- Au moins cinq campagnes et plusieurs sites externes.
- Version et date de disponibilité de chaque feature pour empêcher la fuite.

## Critères de validation

1. Optimisation uniquement avec `GroupKFold` sur les années d'entraînement.
2. Dernière campagne entièrement intacte pour le test final.
3. Aucun identifiant d'essai partagé entre entraînement et test.
4. Métriques globales et par espèce avec taille d'échantillon.
5. Comparaison à une baseline par espèce.
6. Contrôle de dérive avant chaque prédiction et réentraînement.
