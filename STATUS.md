# STATUS — nuit du 9 au 10 juillet 2026

## Fait
- **Chemin live validé sans Docker ni crédits** : Ollama local comme faux proxy Fireworks
  (`FIREWORKS_MODE=live FIREWORKS_BASE_URL=http://localhost:11434/v1 FIREWORKS_API_KEY=ollama ALLOWED_MODELS=<modèle> make eval`).
  Client OpenAI réel, usage réel, résolution ALLOWED_MODELS : tout fonctionne.
- **Leçon modèles reasoning** (gemma4 via Ollama) : le raisonnement consomme le budget `max_tokens`
  et le contenu final arrive vide/tronqué. Durci dans `src/fireworks.py` (`extract_text` : strip
  `<think>`, repli sur le champ reasoning). Comparatif éval (19 tâches, 13 escalades) :
  - mistral 7B (non-reasoning), budgets serrés : **16/19, 1 576 tokens** (échecs = erreurs de calcul d'un 7B)
  - gemma4 (reasoning), budgets ×3 : **17/19, 3 526 tokens**
  → au launch day, préférer un modèle non-thinking (kimi ?) ou budgéter large pour minimax-m3 ;
  à calibrer avec les vrais modèles dès les crédits reçus (`escalation.model_preference` + `max_tokens`).
- Formats I/O extraits du Participant Guide et implémentés (`/input/tasks.json` → `/output/results.json`).
- Pipeline complet en MODE MOCK : solveurs → local → gate → escalade simulée avec comptage de tokens.
- `config.yaml` : tout paramétrable (seuils, mapping catégorie→modèle, max_tokens, escalade, cache).
- 19 fixtures d'éval : 8 practice tasks du guide (practice-04 complétée avec un paragraphe maison) + 11 variantes couvrant les 8 catégories.
- `eval/run_eval.py` : accuracy vérifiée + optimiste, tokens simulés, tableau par catégorie.
- Dockerfile CPU-only linux/amd64, GGUF (Qwen2.5-3B-Instruct Q4_K_M) téléchargé au build.
- Makefile : setup / eval / build / run / size. Git initialisé.

## Reste à faire (par priorité)
1. `make setup-llm && make model` puis `make eval` : mesurer l'accuracy réelle du LLM local et le temps par tâche (budget 10 min pour 19 tâches sur 2 vCPU — si trop lent, réduire `local.max_tokens` ou passer `gate.self_consistency.enabled: false`).
2. `make build && make run && make size` : valider le conteneur de bout en bout (⚠️ Docker indisponible sur cette machine au 9/07 au soir — démarrer Docker Desktop d'abord ; build llama-cpp via roues CPU précompilées, si l'index est indisponible voir le commentaire dans le Dockerfile).
3. Quand les crédits Fireworks arrivent : `.env` + `FIREWORKS_MODE=live`, éval sur 2-3 tâches d'abord (soumissions rate-limited).
4. Calibrer les seuils du gate sur l'éval locale : viser 17/19, escalader math/logic/debug si le local est faible (`escalation.always`).
5. Pousser l'image en public (linux/amd64) et soumettre. Deadline : 11 juillet 18h CET.

## Points d'attention
- `ZERO_API_CALLS` n'est qu'un flag, mais CLAUDE.md recommande de garder quelques escalades réelles.
- Le gate math/logic est superficiel (présence d'un nombre, d'un nom) : la self-consistency locale (activée pour math/logic) est la vraie défense. À chronométrer dans le conteneur.
- practice-04 du guide contient « [your own sample paragraph here] » : remplacée par un paragraphe maison dans les fixtures.
