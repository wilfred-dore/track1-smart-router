# STATUS — 9 juillet 2026

## Fait
- Formats I/O extraits du Participant Guide et implémentés (`/input/tasks.json` → `/output/results.json`).
- Pipeline complet en MODE MOCK : solveurs → local → gate → escalade simulée avec comptage de tokens.
- `config.yaml` : tout paramétrable (seuils, mapping catégorie→modèle, max_tokens, escalade, cache).
- 19 fixtures d'éval : 8 practice tasks du guide (practice-04 complétée avec un paragraphe maison) + 11 variantes couvrant les 8 catégories.
- `eval/run_eval.py` : accuracy vérifiée + optimiste, tokens simulés, tableau par catégorie.
- Dockerfile CPU-only linux/amd64, GGUF (Qwen2.5-3B-Instruct Q4_K_M) téléchargé au build.
- Makefile : setup / eval / build / run / size. Git initialisé.

## Reste à faire (par priorité)
1. `make setup-llm && make model` puis `make eval` : mesurer l'accuracy réelle du LLM local et le temps par tâche (budget 10 min pour 19 tâches sur 2 vCPU — si trop lent, réduire `local.max_tokens` ou passer `gate.self_consistency.enabled: false`).
2. `make build && make run && make size` : valider le conteneur de bout en bout (build llama-cpp via roues CPU précompilées — si l'index est indisponible, voir le commentaire dans le Dockerfile).
3. Quand les crédits Fireworks arrivent : `.env` + `FIREWORKS_MODE=live`, éval sur 2-3 tâches d'abord (soumissions rate-limited).
4. Calibrer les seuils du gate sur l'éval locale : viser 17/19, escalader math/logic/debug si le local est faible (`escalation.always`).
5. Pousser l'image en public (linux/amd64) et soumettre. Deadline : 11 juillet 18h CET.

## Points d'attention
- `ZERO_API_CALLS` n'est qu'un flag, mais CLAUDE.md recommande de garder quelques escalades réelles.
- Le gate math/logic est superficiel (présence d'un nombre, d'un nom) : la self-consistency locale (activée pour math/logic) est la vraie défense. À chronométrer dans le conteneur.
- practice-04 du guide contient « [your own sample paragraph here] » : remplacée par un paragraphe maison dans les fixtures.
