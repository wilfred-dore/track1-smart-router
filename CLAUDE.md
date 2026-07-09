# CLAUDE.md — AMD Developer Hackathon Act II · Track 1

## Objectif
Livrer une image Docker qui **QUALIFIE** au scoring Track 1, puis minimiser les tokens.
Deadline : 11 juillet 2026. Développeur solo (Wilfred). Priorité : vitesse, robustesse, zéro sur-ingénierie.

## Le barème (à connaître par cœur)
- **19 tâches fixes**, jugées par un LLM-judge. Tous les scores sont des n/19.
- **Gate d'accuracy = 80 %.** Donc : 15/19 = 78,9 % → **RECALÉ**. 16/19 = 84,2 % → **PASSÉ**.
- Une fois le gate passé, le classement se fait **uniquement sur le nombre de tokens Fireworks**.
- **Seuls les tokens routés via `FIREWORKS_BASE_URL` comptent.** L'inférence locale = 0 token.
- Le leader actuel : **4 268 tokens à 84,2 %**. Les concurrents à 89,5 % sont DERRIÈRE (accuracy en trop = tokens gaspillés).
- **Cible : 16–17/19, le moins de tokens possible.** Ne PAS chercher 19/19.
- Le LLM-judge n'est pas parfaitement déterministe → garder une petite marge (viser 17, pas 16 pile).

## Contraintes d'exécution (NON négociables)
- Environnement de grading : **4 Go RAM, 2 vCPU, PAS DE GPU**.
- Modèle local : **2B–3B quantisé 4-bit** tient confortablement. Un 7B 4-bit remplit toute la RAM → interdit en pratique.
- **Aucun runtime (Ollama, vLLM…) n'est préinstallé** → les poids doivent être **bundlés dans l'image Docker**. Utiliser `llama-cpp-python` (GGUF) ou équivalent CPU-only.
- Image Docker : **publiquement pullable**, manifest **linux/amd64**, **≤ 10 Go compressée**.
- **Aucune réponse en dur / cachée** : l'évaluation utilise des variantes inédites des tâches.
- Soumissions **rate-limited** → tester en local AVANT de soumettre.

## Modèles Fireworks autorisés (sinon → MODEL_VIOLATION)
`minimax-m3`, `kimi-k2p7-code`, `gemma-4-31b-it`, `gemma-4-26b-a4b-it`, `gemma-4-31b-it-nvfp4`

⚠️ Gemma sur Fireworks est **on-demand** : il faut le déployer (404 = non déployé, pas interdit) et il facture **~7 $/h même à l'arrêt**. Ne pas l'utiliser par défaut. Les orgas confirment qu'on n'a pas besoin de Gemma pour passer le gate.

## Les 8 catégories de tâches
factual Q&A · math reasoning · sentiment · summarization · NER · code debugging · logic puzzles · code generation

Heuristique : sentiment / NER / factuel simple / résumé → **local ou déterministe**.
math / logique / debug / génération de code → **escalade probable**.

## Pourquoi 85 soumissions sur 94 sont RECALÉES
Statuts d'échec : `PULL_ERROR` (image non publique / mauvais tag), `RUNTIME_ERROR` (ne tourne pas sur linux/amd64), `TIMEOUT`, `INVALID_RESULTS_SCHEMA`, `MODEL_VIOLATION`, `IMAGE_TOO_LARGE`, `ACCURACY_GATE_FAILED`, `ZERO_API_CALLS`.

**La majorité des échecs sont de la PLOMBERIE, pas de l'intelligence.** Priorité absolue : un conteneur qui démarre, respecte le schéma de sortie, et finit dans les temps.

⚠️ `ZERO_API_CALLS` = « l'évaluateur n'a vu aucun appel modèle ». Le 100 % local est donc **risqué**. Prévoir au moins quelques appels Fireworks.

## Architecture imposée
```
tâche → [1] solveurs déterministes (regex/règles)      → 0 token
      → [2] modèle local 2-3B 4-bit bundlé (CPU)       → 0 token
      → [3] gate de confiance (self-consistency locale) → 0 token
      → [4] escalade Fireworks : SEULEMENT si nécessaire, modèle le moins cher suffisant
```
Sur les appels Fireworks : **contrat de sortie strict** (`max_tokens` serré, « réponds uniquement la valeur », stop sequences), contexte compressé, cache sémantique.

## Règles d'or
1. **Aucune boucle à l'inférence.** Pas de self-refine, pas de retry spéculatif : chaque tour = des tokens = rang perdu.
2. **Tout piloté par config** (`config.yaml`) : seuils de gate, mapping catégorie→modèle, `max_tokens`, escalade on/off. Jamais en dur.
3. **Mode MOCK obligatoire** : le pipeline doit tourner de bout en bout **sans clé Fireworks** (mock qui simule l'escalade + compte les tokens). On code sans crédits.
4. **Secrets uniquement en variables d'env** (`FIREWORKS_BASE_URL`, `FIREWORKS_API_KEY`). Jamais commités.
5. Calibration **sur l'eval local uniquement** (les soumissions sont rate-limited, le grading set est caché). Ne jamais sur-ajuster le leaderboard.

## Style de travail
- Lire le **Participant Guide** en premier pour le format I/O exact, les variables d'env et les *practice tasks*. Ne rien inventer sur le schéma.
- Plan court avant les grosses modifs. Demander avant toute install lourde.
- Commits petits et fréquents. Tenir `STATUS.md` à jour (ce qui marche / ce qui reste).
- Boucle agentique autorisée : `code → make eval → lire tokens+accuracy → corriger`, avec **critère d'arrêt explicite** (accuracy ≥ 16/19 en local ET tokens en baisse, ou N itérations).
