---
name: laserstudio-devices
description: Manage Laser Studio devices (instruments and stage) via the laserstudio MCP server, inspect their status, and report their state. Use when the user asks to list instruments, check device/peripheral status, read or update instrument settings, get the stage position, or produce a state report of a running Laser Studio setup.
---

# Laser Studio — gestion et état des périphériques

Il s'agit ici d'utiliser laserstudio pour gérer les périphériques, connaitre leur status et avoir un état sur eux.

Cette skill s'appuie sur le serveur MCP `project-0-laserstudio-laserstudio`, qui pilote une instance Laser Studio **en cours d'exécution** via son API REST. Toujours lire le descripteur JSON d'un outil (`mcps/project-0-laserstudio-laserstudio/tools/<outil>.json`) avant un premier appel pour confirmer ses paramètres.

## Outils disponibles

| Objectif | Outil MCP | Paramètres |
|---|---|---|
| Lister les périphériques | `list_instruments` | aucun |
| Lire les réglages d'un périphérique | `get_instrument_settings` | `label` (string) |
| Modifier les réglages d'un périphérique | `set_instrument_settings` | `label` (string), `settings` (objet) |
| Position de la platine (stage) | `get_stage_position` | aucun |
| État du magic focus | `magic_focus` | aucun (sans paramètre = lecture de l'état) |
| Nombre d'images moyennées (caméra) | `get_averaging` | aucun |

## Workflow : faire l'état des périphériques

1. **Lister** les périphériques avec `list_instruments`. Chaque entrée fournit au moins `type` et `label`. Le `label` est la clé utilisée par tous les autres outils.
2. **Pour chaque périphérique pertinent**, lire ses réglages avec `get_instrument_settings` en passant son `label` exact.
3. **Compléter l'état global** si utile : `get_stage_position`, `magic_focus` (sans paramètre), `get_averaging`.
4. **Synthétiser** sous forme de tableau (voir modèle ci-dessous).

## Workflow : modifier un réglage

1. Lire l'état courant avec `get_instrument_settings` pour connaître les clés exactes attendues.
2. Appeler `set_instrument_settings` avec le `label` et un objet `settings` ne contenant **que** les clés à modifier.
3. Relire avec `get_instrument_settings` pour confirmer la prise en compte.

Avant toute modification, annoncer clairement à l'utilisateur le périphérique ciblé et la valeur appliquée. Ne pas modifier un réglage qui n'a pas été explicitement demandé.

## Gestion des erreurs

Les outils échouent avec un message préfixé d'un code machine :

- `INSTRUMENT_NOT_FOUND` : le `label` est inconnu → relancer `list_instruments` et utiliser un `label` exact (sensible à la casse).
- `DEVICE_UNAVAILABLE` : le périphérique ne répond pas → le signaler dans l'état comme indisponible, ne pas réessayer en boucle.
- `INVALID_PARAMETER` : un paramètre/réglage est invalide → vérifier les clés via `get_instrument_settings`.
- `CONNECTION_ERROR` : Laser Studio n'est pas joignable → vérifier que l'instance tourne et que l'API REST est accessible.

## Modèle de rapport d'état

```markdown
## État des périphériques Laser Studio

| Périphérique (label) | Type | Statut | Réglages clés |
|---|---|---|---|
| <label> | <type> | OK / Indisponible | <réglages résumés> |

**Platine** : position (x, y, ...) = <get_stage_position>
**Magic focus** : <état>
**Moyennage caméra** : <get_averaging>
```
