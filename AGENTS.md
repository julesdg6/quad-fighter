# AGENTS.md

## Project
Quad Fighter

## Summary
Quad Fighter is a Python prototype for a side-scrolling arcade beat-em-up.  
The goal is to capture the gameplay feel of classic co-op brawlers like TMNT, Double Dragon, and similar belt-scroll fighters, while using simple procedural vector-style graphics instead of bitmap sprites.

This project should begin as a greybox prototype and stay focused on gameplay first.

---

## Core Goal
Build a small, playable, extendable beat-em-up prototype in Python using `pygame-ce`.

The first milestone is not a full game.  
It is a tight playable prototype with:
- one player
- one enemy
- one screen
- movement
- jump
- one attack
- basic enemy AI
- hit detection
- knockback
- health
- simple HUD

---

## Technical Constraints
- Use Python only
- Use `pygame-ce`
- Keep dependencies minimal
- Do not use bitmap sprites or sprite sheets
- Render characters and effects using procedural/vector-like primitives only:
  - lines
  - circles
  - rectangles
  - polygons
- Keep files small and readable
- Keep architecture modular but simple
- Avoid over-engineering

---

## Design Priorities
Prioritize these in order:

1. Playability
2. Readability of code
3. Responsiveness of controls
4. Combat feel
5. Extendability
6. Visual polish

Do not sacrifice gameplay feel in order to build elaborate systems too early.

---

## Visual Direction
The prototype should use simple greybox visuals.

Characters should feel like:
- side-on arcade fighters
- strong readable silhouettes
- procedural placeholder figures
- vector-drawn limbs and bodies

Influence:
- classic belt-scroll brawlers for gameplay
- Flashback / Prince of Persia style movement energy for the long-term visual direction

Important:
Do not attempt a full animation system too early.  
Start with simple shapes and readable placeholder motion.

---

## Phase 1 Scope
Build only the minimum playable prototype.

### Required features
- fixed-size game window
- main game loop at 60 FPS
- one player character
- one enemy
- left/right movement
- up/down movement for lane depth
- jump
- one attack button
- simple enemy chase AI
- hit detection
- knockback
- health values
- simple HUD

### Controls
- Arrow keys = move
- Space = jump
- Z = attack

---

## Out of Scope for Now
Do not add these unless explicitly requested:
- online multiplayer
- local 4-player support yet
- menus
- settings screens
- save systems
- sound system beyond basic placeholders
- particle system beyond minimal effects
- bitmap art
- sprite sheets
- content editors
- networking
- ECS refactors
- advanced physics engines
- asset pipelines
- large framework abstractions

---

## Architecture Guidance
Use a simple modular layout.

Suggested structure:

- `main.py` for bootstrapping and game loop
- `player.py` for player behaviour
- `enemy.py` for enemy behaviour
- `combat.py` for hit detection / damage / knockback if needed
- `render.py` for shared drawing helpers if needed
- `README.md` for run instructions
- `requirements.txt` for dependencies

Prefer a small number of clear files over many abstractions.

### Rules
- Separate update logic from draw logic
- Keep state easy to understand
- Prefer plain classes and simple data flow
- Avoid giant god objects
- Avoid speculative abstractions for future features
- Build only what is needed for the current milestone

---

## Implementation Behaviour
When working on this project:

1. First explain what files you plan to create or modify
2. Then implement the smallest version that works
3. Then run the game if possible
4. Then fix any syntax/runtime issues
5. Keep iteration small and grounded

If a requested feature is too large, break it into the next smallest playable step.

---

## Coding Style
- Clear, direct Python
- Small functions
- Simple classes
- Minimal dependencies
- Readability over cleverness
- Comments only where genuinely useful
- Avoid unnecessary patterns or indirection

---

## Success Criteria for Phase 1
Phase 1 is successful when:
- the project runs cleanly
- the player can move, jump, and attack
- the enemy can move and interact
- combat feedback is visible
- the codebase is clean enough to extend into a fuller brawler later

---

## Future Direction
Once Phase 1 is stable, future phases may add:
- multiple enemies
- scrolling stages
- combo chains
- grabs / throws
- multiple local players
- better procedural fighter rigs
- thematic reskinning

But do not build these yet unless asked.
