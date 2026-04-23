# Quad Fighter Prototype

## Requirements

To run the game, install the required dependencies:

```bash
pip install -r requirements.txt
```

## Controls

- Arrow keys: Move (left/right and up/down lane depth)
- Space: Jump
- Z: Primary Attack
- X: Secondary Attack

## Running the Game

```bash
python main.py
```

## Screenshots

### Gameplay Overview

![Gameplay overview](docs/screenshots/gameplay-overview.png)

### Combat Hit Feedback

![Combat hit feedback](docs/screenshots/combat-hit-feedback.png)

## Features Implemented

- Side-scrolling stage with camera follow and world-space coordinates
- Player movement with lane-based depth, jump, and two attacks
- Progressive enemy spawning as player advances
- Enemy AI with chase + melee attacks, cooldown pacing, and player damage
- End-of-level boss encounter with distinct silhouette and health bar
- Simple combat system with distinct primary/secondary attack hitboxes and tuning
- Enemy hurt stun, knockback, and brief hit flash feedback
- Interactive environment objects (crates, barrels, and pickup pipe weapon)
- Breakable objects with health and simple break flash effect
- Weapon pickup that boosts attack range/damage for a limited number of hits
- Health values and simple HUD (enemy count, stage progress, weapon state)
- Visible lane/floor band for depth readability
- Procedural named-pose fighter animation (idle/walk/jump/attack/hurt)
- 60 FPS game loop

## Next Steps

1. Add additional enemy behavior variety
2. Expand player combat options
3. Improve procedural character posing
4. Expand to local co-op
5. Add stage progression
