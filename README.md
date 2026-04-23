# Quad Fighter Prototype

## Requirements

To run the game, install the required dependencies:

```bash
pip install -r requirements.txt
```

## Controls

- Arrow keys: Move (left/right and up/down lane depth)
- Space: Jump
- Z: Attack

## Running the Game

```bash
python main.py
```

## Features Implemented

- Player movement with lane-based depth
- Basic enemy AI (chase player)
- Simple combat system with forward attack hitbox and attack cooldown
- Enemy hurt stun, knockback, and brief hit flash feedback
- Two-enemy one-screen flow with clear message after both are defeated
- Health values and simple HUD (including enemy HP)
- Basic hitbox visualization
- Visible lane/floor band for depth readability
- Procedural named-pose fighter animation (idle/walk/jump/attack/hurt)
- 60 FPS game loop

## Next Steps

1. Add additional enemy behavior variety
2. Expand player combat options
3. Improve procedural character posing
4. Expand to local co-op
5. Add stage progression
