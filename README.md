# Track 1 — Smart Router (AMD Developer Hackathon ACT II)

Routeur de tâches NL : maximum de réponses à **0 token Fireworks**, escalade
uniquement quand nécessaire. Objectif : passer le gate d'accuracy (80 %, soit
16/19) puis minimiser les tokens facturés via `FIREWORKS_BASE_URL`.

## Architecture

```
tâche → [1] solveurs déterministes (regex/règles)        → 0 token
      → [2] LLM local GGUF 2-3B 4-bit, CPU (bundlé)      → 0 token
      → [3] gate de confiance (heuristiques +            → 0 token
            self-consistency locale)
      → [4] escalade Fireworks (modèle choisi dans        → tokens comptés
            ALLOWED_MODELS, contrat de sortie serré)
```

Un seul passage par tâche, jamais de boucle. Tout est piloté par
[config.yaml](config.yaml) : seuils de gate, mapping catégorie→modèle,
`max_tokens`, escalade on/off, cache on/off.

## Formats I/O (Participant Guide)

- Entrée : `/input/tasks.json` — `[ { "task_id": "...", "prompt": "..." } ]`
- Sortie : `/output/results.json` — `[ { "task_id": "...", "answer": "..." } ]`
- Env injecté par le harness : `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`,
  `ALLOWED_MODELS` (lu à l'exécution, jamais en dur).

## Modes (variable d'env `FIREWORKS_MODE`)

| Mode  | Comportement |
|-------|--------------|
| `mock` | aucun appel réseau, réponses simulées, tokens comptés (estimation) |
| `live` | appels réels via `FIREWORKS_BASE_URL` |
| `auto` (défaut) | `live` si `FIREWORKS_API_KEY` présent, sinon `mock` — à l'évaluation le harness injecte la clé, donc l'image passe en live sans modification |

## Quickstart (sans clé Fireworks, sans GPU)

```bash
make setup      # venv + deps coeur
make eval       # 19 fixtures : accuracy + tokens simulés, tableau par catégorie
make run-local  # pipeline complet en local (formats du guide)
```

Inférence locale réelle (optionnelle en dev, incluse dans l'image Docker) :

```bash
make setup-llm  # llama-cpp-python
make model      # télécharge le GGUF (~2 Go) dans models/
make eval       # ré-évalue avec le LLM local actif
```

## Docker (soumission)

```bash
make build      # buildx linux/amd64, GGUF téléchargé AU BUILD et bundlé
make run        # exécute l'image comme le harness (mock forcé)
make size       # vérifie la taille compressée (< 10 Go exigé)
```

Publication : `docker tag track1-smart-router:latest <registry>/<image>:latest`
puis `docker push` (l'image doit être **publique**).

## Structure

```
config.yaml          tous les réglages (rien en dur dans le code)
src/solvers.py       solveurs déterministes (math, sentiment, NER, factuel)
src/local_llm.py     wrapper llama-cpp-python (GGUF, CPU-only)
src/gate.py          gate de confiance à coût nul
src/fireworks.py     client OpenAI-compatible + MockFireworksClient
src/router.py        cascade + classification de catégorie
src/main.py          entrée/sortie aux formats du guide
eval/tasks/          19 fixtures (8 practice tasks du guide + 11 variantes)
eval/run_eval.py     accuracy n/19 + tokens, tableau par catégorie
```

## Checklist avant soumission

- [ ] `make eval` ≥ 16/19 en local avec le LLM local actif
- [ ] `make build && make run` : `results.json` valide, exit code 0, < 10 min
- [ ] `make size` < 10 Go
- [ ] image poussée en **public** avec manifest **linux/amd64**
- [ ] aucun secret ni `.env` dans l'image
