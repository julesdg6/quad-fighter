import math

import pygame

BASE_WALK_PHASE_SPEED = 4.5        # snappier arcade walk cycle (was 3.2)
WALK_PHASE_SPEED_FROM_MOVE = 3.5   # (was 2.8)
IDLE_BOB_FREQUENCY = 3.0           # slightly faster subtle guard bob (was 2.2)
IDLE_BOB_AMPLITUDE = 0.8           # more subtle (was 1.4)
ATTACK_BASE_REACH = 0.28           # (was 0.30)
ATTACK_REACH_EXTENSION = 0.62      # reduced punch reach so fist stays readable (was 0.95)
ATTACK_ANTICIPATION_END = 0.24     # fast startup – arcade-snappy punch (was 0.34)
ATTACK_STRIKE_END = 0.54           # (was 0.62)
MIN_ATTACK_PHASE_DURATION = 0.05
MAX_ATTACK_ANTICIPATION_END = 0.9
MAX_ATTACK_STRIKE_END = 0.95
MIN_PHASE_DIVISOR = 0.001
JUMP_BOB_OFFSET = 4.0
SHOULDER_SPAN_RATIO = 0.33         # broad brawler shoulders (was 0.26)
HIP_SPAN_RATIO = 0.13              # narrower hips for V-taper (was 0.16)
WAIST_SPAN_RATIO = 0.09
WAIST_POSITION_RATIO = 0.52        # waist sits higher for blockier torso (was 0.55)
WAIST_TILT_FACTOR = 0.64
BELT_DROP_RATIO = 0.30
SHADOW_DEPTH_BASE_SCALE = 0.82
SHADOW_DEPTH_SCALE_RANGE = 0.35
JOINT_SIZE_RATIO = 0.25            # slightly smaller joint dots (was 0.30)
MIN_HAND_RADIUS = 3
HAND_SIZE_RATIO = 0.09
MIN_FOOT_LENGTH = 8
FOOT_LENGTH_RATIO = 0.30           # bigger boots (was 0.26)
MIN_FOOT_HEIGHT = 4
FOOT_HEIGHT_RATIO = 0.09           # chunkier boot height (was 0.06)
NECK_WIDTH_RATIO = 0.11
IDLE_STANCE_DROP_RATIO = 0.08      # deep fighting guard crouch (was 0.035)
FIST_WIDTH_MULTIPLIER = 1.9        # chunky brawler fists (was 1.8 original, 2.2 too large)
WALK_BOB_AMPLITUDE = 0.35          # less floaty vertical bob during walk (was 0.55)

# Face feature colours / darkening amounts
EYE_SCLERA_COLOR = (238, 228, 212)
EYE_IRIS_COLOR = (18, 14, 12)
NOSE_DARKEN_AMOUNT = 24
MOUTH_DARKEN_AMOUNT = 36


def _joint_midpoint(a, b, lift, bend):
    return (
        int((a[0] + b[0]) * 0.5 + bend),
        int((a[1] + b[1]) * 0.5 - lift),
    )


def _draw_limb(screen, color, start, mid, end, width):
    pygame.draw.line(screen, color, start, mid, width)
    pygame.draw.line(screen, color, mid, end, width)


def _segment_polygon(start, end, start_width, end_width):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max(1.0, math.hypot(dx, dy))
    nx = -dy / length
    ny = dx / length
    sw = start_width * 0.5
    ew = end_width * 0.5
    return [
        (int(start[0] + nx * sw), int(start[1] + ny * sw)),
        (int(start[0] - nx * sw), int(start[1] - ny * sw)),
        (int(end[0] - nx * ew), int(end[1] - ny * ew)),
        (int(end[0] + nx * ew), int(end[1] + ny * ew)),
    ]


def _draw_segment(screen, color, start, end, start_width, end_width):
    pygame.draw.polygon(
        screen,
        color,
        _segment_polygon(start, end, start_width, end_width),
    )


def _draw_bent_limb(
    screen,
    upper_color,
    lower_color,
    start,
    mid,
    end,
    upper_width,
    lower_width,
):
    _draw_segment(screen, upper_color, start, mid, upper_width, max(2, upper_width * 0.88))
    _draw_segment(screen, lower_color, mid, end, lower_width, max(2, lower_width * 0.78))
    pygame.draw.circle(
        screen,
        lower_color,
        mid,
        max(2, int(min(upper_width, lower_width) * JOINT_SIZE_RATIO)),
    )


def _point_lerp(a, b, ratio):
    return (
        int(a[0] + (b[0] - a[0]) * ratio),
        int(a[1] + (b[1] - a[1]) * ratio),
    )


def get_depth_scale(ground_y, lane_min, lane_max):
    if lane_max <= lane_min:
        return SHADOW_DEPTH_BASE_SCALE
    lane_ratio = (ground_y - lane_min) / (lane_max - lane_min)
    lane_ratio = max(0.0, min(1.0, lane_ratio))
    return SHADOW_DEPTH_BASE_SCALE + lane_ratio * SHADOW_DEPTH_SCALE_RANGE


def _clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def _draw_weapon_at_hand(screen, weapon_name, front_hand, facing, width, height, attack_extension):
    """Draw the carried weapon extending from the fighter's front hand."""
    hx, hy = front_hand
    ext = max(0.0, min(1.0, attack_extension))

    if weapon_name in ("pipe", "bat"):
        # Long wooden/metal stick – extends horizontally from hand
        stick_len = int(width * (0.55 + 0.35 * ext))
        stick_w = max(5, int(width * 0.07))
        # Baseball bat has a tapered barrel; pipe is uniform
        bat_barrel_taper = int(stick_len * 0.22) if weapon_name == "bat" else 0
        base_color = (150, 100, 50) if weapon_name == "bat" else (150, 150, 158)
        dark_color = (100, 65, 30) if weapon_name == "bat" else (90, 90, 100)
        tip_x = hx + facing * stick_len
        # Main stick body (tapered at barrel end for bat)
        pts = [
            (hx, hy - stick_w // 2),
            (tip_x - facing * bat_barrel_taper, hy - (stick_w // 2 + bat_barrel_taper // 3)),
            (tip_x, hy - (stick_w // 2 + bat_barrel_taper // 2)),
            (tip_x, hy + (stick_w // 2 + bat_barrel_taper // 2)),
            (tip_x - facing * bat_barrel_taper, hy + (stick_w // 2 + bat_barrel_taper // 3)),
            (hx, hy + stick_w // 2),
        ]
        pygame.draw.polygon(screen, base_color, pts)
        pygame.draw.polygon(screen, dark_color, pts, 1)

    elif weapon_name == "whip":
        # Whip: curved line from hand, snapping forward during attack
        seg = max(4, int(width * 0.14))
        segs = 5
        pts = [(hx, hy)]
        for i in range(1, segs + 1):
            t = i / segs
            droop = int(height * 0.08 * t * (1.0 - ext * 0.6))
            px = hx + facing * int(seg * i * (0.8 + 0.4 * ext))
            py = hy + droop
            pts.append((px, py))
        if len(pts) >= 2:
            pygame.draw.lines(screen, (160, 100, 40), False, pts, 3)
            # Cracker tip
            pygame.draw.circle(screen, (220, 160, 80), pts[-1], 3)

    elif weapon_name == "chain":
        # Chain: series of oval links from hand
        link_spacing = max(8, int(width * 0.1))
        n_links = 4
        droop_per = int(height * 0.025 * (1.0 - ext * 0.5))
        lw, lh = max(6, link_spacing - 2), max(4, int(link_spacing * 0.45))
        for i in range(n_links):
            lx = hx + facing * link_spacing * i - lw // 2
            ly = hy + droop_per * i - lh // 2
            link_rect = pygame.Rect(lx, ly, lw, lh)
            pygame.draw.ellipse(screen, (190, 190, 200), link_rect)
            pygame.draw.ellipse(screen, (110, 110, 120), link_rect, 2)

    elif weapon_name == "nunchucks":
        # Nunchucks: one stick held in hand, other swings out on a short cord
        stick_len = max(16, int(height * 0.17))
        stick_w = max(5, int(width * 0.07))
        cord_len = max(10, int(stick_len * 0.55))
        swing = ext * 0.9  # swing angle proportion
        # Held stick along the arm
        s1_end = (hx + facing * stick_len, hy)
        pts1 = [
            (hx, hy - stick_w // 2),
            (s1_end[0], s1_end[1] - stick_w // 2),
            (s1_end[0], s1_end[1] + stick_w // 2),
            (hx, hy + stick_w // 2),
        ]
        pygame.draw.polygon(screen, (80, 52, 28), pts1)
        pygame.draw.polygon(screen, (50, 32, 14), pts1, 1)
        # Short cord
        cord_end_x = s1_end[0] + facing * int(cord_len * (0.4 + 0.6 * swing))
        cord_end_y = s1_end[1] + int(cord_len * (0.6 - 0.5 * swing))
        pygame.draw.line(screen, (180, 180, 180), s1_end, (cord_end_x, cord_end_y), 2)
        # Swinging stick
        s2_end = (cord_end_x + facing * stick_len, cord_end_y)
        pts2 = [
            (cord_end_x, cord_end_y - stick_w // 2),
            (s2_end[0], s2_end[1] - stick_w // 2),
            (s2_end[0], s2_end[1] + stick_w // 2),
            (cord_end_x, cord_end_y + stick_w // 2),
        ]
        pygame.draw.polygon(screen, (80, 52, 28), pts2)
        pygame.draw.polygon(screen, (50, 32, 14), pts2, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Gauntlet-style archetype overlay helpers
# Each function is called at the end of draw_fighter() when palette["archetype"]
# matches the corresponding class.  All coordinates come from draw_fighter()'s
# local variables and are passed explicitly so the helpers stay side-effect-free.
#
# Proportion constants use head_radius (hr) as the unit so the overlays scale
# consistently with the overall character size.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Warrior proportions ────────────────────────────────────────────────────────
_HELM_TOP_RATIO    = 0.92   # helmet top above head_center, in units of head_radius
_HELM_BASE_RATIO   = 0.08   # helmet base below head_center
_HORN_REACH_RATIO  = 1.28   # how far the horn tip extends sideways (x)
_HORN_HEIGHT_RATIO = 0.96   # how far the horn tip extends upward (y)
_KILT_FRINGE_COUNT = 5      # vertical fringe lines on the warrior kilt

# ── Wizard proportions ────────────────────────────────────────────────────────
_HAT_BRIM_RATIO    = 1.10   # hat brim half-width in units of head_radius
_HAT_TIP_RATIO     = 3.20   # hat tip height above head_center
_HAT_LEAN_RATIO    = 0.22   # how much the hat tip leans backward (away from facing)
_ROBE_FOLD_SEGS    = 3      # visible fold lines on the robe (divides robe into N+1 panels)

def _draw_archetype_warrior(
    screen, palette, head_center, head_radius,
    waist_left, waist_right, left_hip, right_hip,
    bottom_y, hip_y, upper_leg_width,
):
    """Gauntlet Warrior: horned bronze helmet + leather kilt."""
    helm_color = palette.get("helm_color", (148, 116, 62))
    kilt_color = palette.get("kilt_color", (106, 60, 26))
    cx, cy = head_center
    hr     = head_radius
    top    = cy - int(hr * _HELM_TOP_RATIO)
    base   = cy + int(hr * _HELM_BASE_RATIO)

    # Helmet bowl
    helm_pts = [
        (cx - int(hr * 0.90), base),
        (cx - int(hr * 0.86), top + int(hr * 0.12)),
        (cx - int(hr * 0.38), top - int(hr * 0.20)),
        (cx + int(hr * 0.38), top - int(hr * 0.20)),
        (cx + int(hr * 0.86), top + int(hr * 0.12)),
        (cx + int(hr * 0.90), base),
    ]
    pygame.draw.polygon(screen, helm_color, helm_pts)
    brow_col = tuple(max(0, c - 38) for c in helm_color)
    pygame.draw.line(screen, brow_col,
                     (cx - int(hr * 0.88), base),
                     (cx + int(hr * 0.88), base),
                     max(2, int(hr * 0.22)))
    hi_col = tuple(min(255, c + 36) for c in helm_color)
    pygame.draw.line(screen, hi_col,
                     (cx - int(hr * 0.30), top - int(hr * 0.08)),
                     (cx + int(hr * 0.30), top - int(hr * 0.08)), 1)

    # Left horn (sweeps up and outward)
    lh_pts = [
        (cx - int(hr * 0.76),             top + int(hr * 0.08)),
        (cx - int(hr * 0.88),             base),
        (cx - int(hr * _HORN_REACH_RATIO), top - int(hr * 0.52)),
        (cx - int(hr * 1.06),             top - int(hr * _HORN_HEIGHT_RATIO)),
        (cx - int(hr * 0.80),             top - int(hr * 0.08)),
    ]
    pygame.draw.polygon(screen, helm_color, lh_pts)

    # Right horn (mirror)
    rh_pts = [
        (cx + int(hr * 0.76),             top + int(hr * 0.08)),
        (cx + int(hr * 0.88),             base),
        (cx + int(hr * _HORN_REACH_RATIO), top - int(hr * 0.52)),
        (cx + int(hr * 1.06),             top - int(hr * _HORN_HEIGHT_RATIO)),
        (cx + int(hr * 0.80),             top - int(hr * 0.08)),
    ]
    pygame.draw.polygon(screen, helm_color, rh_pts)

    # Kilt / loincloth (covers upper leg area)
    kilt_top = int((waist_left[1] + waist_right[1]) * 0.5)
    kilt_bot = int(hip_y + (bottom_y - hip_y) * 0.42)
    kx       = int((left_hip[0] + right_hip[0]) * 0.5)
    kht      = int(abs(waist_left[0] - waist_right[0]) * 0.6 + upper_leg_width)
    khb      = int(kht * 1.72)
    kilt_pts = [
        (kx - kht, kilt_top),
        (kx + kht, kilt_top),
        (kx + khb, kilt_bot),
        (kx - khb, kilt_bot),
    ]
    pygame.draw.polygon(screen, kilt_color, kilt_pts)
    fringe = tuple(max(0, c - 26) for c in kilt_color)
    for i in range(_KILT_FRINGE_COUNT):
        t  = (i + 0.5) / _KILT_FRINGE_COUNT
        tx = int(kx - kht + 2 * kht * t)
        bx = int(kx - khb + 2 * khb * t)
        pygame.draw.line(screen, fringe, (tx, kilt_top), (bx, kilt_bot), 1)


def _draw_archetype_valkyrie(
    screen, palette, head_center, head_radius, facing,
    rear_shoulder, rear_hip,
):
    """Gauntlet Valkyrie: winged helmet + off-hand round shield."""
    armor_color = palette.get("armor_color", (130, 145, 175))
    wing_color  = palette.get("wing_color",  (210, 215, 230))
    cx, cy = head_center
    hr     = head_radius
    top    = cy - int(hr * 0.92)
    base   = cy + int(hr * 0.08)

    # Helmet bowl (angular Valkyrie silhouette)
    helm_pts = [
        (cx - int(hr * 0.86), base),
        (cx - int(hr * 0.82), top + int(hr * 0.08)),
        (cx - int(hr * 0.34), top - int(hr * 0.22)),
        (cx + int(hr * 0.34), top - int(hr * 0.22)),
        (cx + int(hr * 0.82), top + int(hr * 0.08)),
        (cx + int(hr * 0.86), base),
    ]
    pygame.draw.polygon(screen, armor_color, helm_pts)
    brow_col = tuple(max(0, c - 36) for c in armor_color)
    pygame.draw.line(screen, brow_col,
                     (cx - int(hr * 0.84), base),
                     (cx + int(hr * 0.84), base),
                     max(2, int(hr * 0.20)))

    # Nose guard: narrow vertical strip
    nose_g_w = max(2, int(hr * 0.16))
    pygame.draw.rect(screen, brow_col,
                     (cx - nose_g_w // 2, base, nose_g_w, int(hr * 0.50)))

    # Wing on the forward-facing side of the helmet
    w_cx = cx + facing * int(hr * 0.72)
    w_cy = (top + base) // 2
    wing_pts = [
        (w_cx,                             w_cy),
        (w_cx + facing * int(hr * 0.36),   w_cy - int(hr * 0.12)),
        (w_cx + facing * int(hr * 1.10),   w_cy - int(hr * 0.68)),
        (w_cx + facing * int(hr * 1.16),   w_cy - int(hr * 0.40)),
        (w_cx + facing * int(hr * 0.52),   w_cy + int(hr * 0.12)),
    ]
    pygame.draw.polygon(screen, wing_color, wing_pts)

    # Round shield on the rear (off-hand) arm
    shield_r  = max(7, int(hr * 0.84))
    shield_cx = rear_shoulder[0] - facing * int(hr * 0.22)
    shield_cy = rear_shoulder[1] + int(hr * 0.68)
    rim_col   = tuple(min(255, c + 28) for c in armor_color)
    pygame.draw.circle(screen, armor_color, (shield_cx, shield_cy), shield_r)
    pygame.draw.circle(screen, rim_col,    (shield_cx, shield_cy), shield_r, 2)
    pygame.draw.circle(screen, rim_col,    (shield_cx, shield_cy), max(2, shield_r // 3))


def _draw_archetype_wizard(
    screen, palette, head_center, head_radius, facing,
    left_hip, right_hip, hip_y, bottom_y,
):
    """Gauntlet Wizard: tall pointed hat + flowing robe (covers legs) + long beard."""
    hat_color   = palette.get("hat_color",   (50, 32, 82))
    robe_color  = palette.get("robe_color",  (168, 164, 180))
    beard_color = palette.get("beard_color", (218, 214, 208))
    cx, cy = head_center
    hr     = head_radius

    # Tall conical hat
    hat_brim_w = int(hr * 1.10)
    hat_base_y = cy - int(hr * 0.78)
    hat_tip_x  = cx - facing * int(hr * 0.22)   # slight backward lean
    hat_tip_y  = cy - int(hr * 3.20)
    hat_cone   = [
        (cx - hat_brim_w, hat_base_y),
        (cx + hat_brim_w, hat_base_y),
        (hat_tip_x,       hat_tip_y),
    ]
    pygame.draw.polygon(screen, hat_color, hat_cone)
    brim_col = tuple(max(0, c - 24) for c in hat_color)
    brim_pts = [
        (cx - hat_brim_w - int(hr * 0.18), hat_base_y - int(hr * 0.08)),
        (cx + hat_brim_w + int(hr * 0.18), hat_base_y - int(hr * 0.08)),
        (cx + hat_brim_w,                  hat_base_y + int(hr * 0.18)),
        (cx - hat_brim_w,                  hat_base_y + int(hr * 0.18)),
    ]
    pygame.draw.polygon(screen, brim_col, brim_pts)

    # Flowing robe skirt: trapezoid from hip level to just below feet
    robe_cx    = int((left_hip[0] + right_hip[0]) * 0.5)
    robe_ht    = int(abs(left_hip[0] - right_hip[0]) * 0.5 + 8)
    robe_hb    = int(robe_ht * 2.18)
    robe_bot_y = bottom_y + 2
    robe_pts   = [
        (robe_cx - robe_ht, hip_y),
        (robe_cx + robe_ht, hip_y),
        (robe_cx + robe_hb, robe_bot_y),
        (robe_cx - robe_hb, robe_bot_y),
    ]
    pygame.draw.polygon(screen, robe_color, robe_pts)
    fold_dark = tuple(max(0, c - 26) for c in robe_color)
    for i in range(3):
        t  = (i + 1) / 4.0
        px = int(robe_cx - robe_ht + 2 * robe_ht * t)
        bx = int(robe_cx - robe_hb + 2 * robe_hb * t)
        pygame.draw.line(screen, fold_dark, (px, hip_y), (bx, robe_bot_y), 1)

    # Long flowing beard
    chin_y   = cy + int(hr * 1.06)
    chin_fwd = cx + facing * int(hr * 0.28)
    beard_pts = [
        (cx - facing * int(hr * 0.46),       chin_y),
        (chin_fwd,                            chin_y),
        (chin_fwd + facing * int(hr * 0.40), chin_y + int(hr * 0.70)),
        (chin_fwd + facing * int(hr * 0.26), chin_y + int(hr * 1.62)),
        (cx,                                 chin_y + int(hr * 2.26)),
        (cx - facing * int(hr * 0.36),       chin_y + int(hr * 1.82)),
        (cx - facing * int(hr * 0.46),       chin_y + int(hr * 1.08)),
    ]
    pygame.draw.polygon(screen, beard_color, beard_pts)
    beard_mid = tuple(max(0, c - 18) for c in beard_color)
    pygame.draw.line(screen, beard_mid,
                     (cx, chin_y + int(hr * 0.20)),
                     (cx, chin_y + int(hr * 1.96)), 1)


def _draw_archetype_elf(
    screen, palette, head_center, head_radius, facing,
    rear_shoulder, rear_hip,
):
    """Gauntlet Elf: pointed hood + quiver on back."""
    hood_color   = palette.get("hood_color",   (38, 98, 40))
    quiver_color = palette.get("quiver_color", (96, 62, 28))
    cx, cy = head_center
    hr     = head_radius

    # Pointed hood / cap: triangle angled to the rear
    h_base_y = cy + int(hr * 0.22)
    h_fwd_x  = cx + facing * int(hr * 0.56)
    h_rear_x = cx - facing * int(hr * 0.78)
    h_tip_x  = cx - facing * int(hr * 1.08)
    h_tip_y  = cy - int(hr * 1.88)
    hood_pts = [(h_fwd_x, h_base_y), (h_rear_x, h_base_y), (h_tip_x, h_tip_y)]
    pygame.draw.polygon(screen, hood_color, hood_pts)
    hood_hi = tuple(min(255, c + 32) for c in hood_color)
    mid_bx  = (h_fwd_x + h_rear_x) // 2
    pygame.draw.line(screen, hood_hi, (mid_bx, h_base_y), (h_tip_x, h_tip_y), 1)

    # Quiver on the back (rear shoulder side)
    q_cx  = rear_shoulder[0] - facing * int(hr * 0.50)
    q_top = rear_shoulder[1] - int(hr * 0.22)
    q_bot = rear_hip[1] + int(hr * 0.30)
    q_w   = max(4, int(hr * 0.50))
    pygame.draw.rect(screen, quiver_color,
                     (q_cx - q_w // 2, q_top, q_w, q_bot - q_top),
                     border_radius=3)
    tuft = tuple(min(255, c + 50) for c in quiver_color)
    for dx_off in (-int(hr * 0.18), 0, int(hr * 0.18)):
        pygame.draw.line(screen, tuft,
                         (q_cx + dx_off, q_top),
                         (q_cx + dx_off - facing * int(hr * 0.22),
                          q_top - int(hr * 0.38)), 1)


def draw_fighter(
    screen,
    body_rect,
    facing,
    palette,
    pose,
    move_ratio=0.0,
    attack_ratio=0.0,
    hurt_ratio=0.0,
    phase_offset=0.0,
    attack_anticipation_end=ATTACK_ANTICIPATION_END,
    attack_strike_end=ATTACK_STRIKE_END,
    hit_region="torso",
    weapon_name=None,
):
    facing = 1 if facing >= 0 else -1
    clamped_attack_ratio = max(0.0, min(1.0, attack_ratio))
    t = pygame.time.get_ticks() / 1000.0 + phase_offset
    walk_phase = t * (BASE_WALK_PHASE_SPEED + move_ratio * WALK_PHASE_SPEED_FROM_MOVE)
    walk_sin = math.sin(walk_phase)
    walk_cos = math.cos(walk_phase)

    width = body_rect.width
    height = body_rect.height
    center_x = body_rect.centerx
    top_y = body_rect.top
    bottom_y = body_rect.bottom

    # Head sized relative to height so it reads as ~1/5 of total body (brawler proportions)
    # Using 0.10 as radius → diameter ≈ 0.20 × height
    head_radius = max(6, int(height * 0.10 * palette.get("head_scale", 1.0)))
    shoulder_span = int(width * palette.get("shoulder_ratio", SHOULDER_SPAN_RATIO))
    hip_span = int(width * palette.get("hip_ratio", HIP_SPAN_RATIO))
    waist_span = int(width * palette.get("waist_ratio", WAIST_SPAN_RATIO))
    torso_len = int(height * 0.35)          # taller torso block (was 0.30)
    upper_arm_width = max(5, int(width * palette.get("arm_width", 0.25)))   # chunky arms (was 0.20)
    lower_arm_width = max(4, int(upper_arm_width * 0.84))
    upper_leg_width = max(6, int(width * palette.get("leg_width", 0.26)))   # stocky legs (was 0.22)
    lower_leg_width = max(5, int(upper_leg_width * 0.82))

    torso_color = palette.get("torso", (170, 170, 170))
    pelvis_color = palette.get("pelvis", torso_color)
    chest_color = palette.get("chest", torso_color)
    head_color = palette.get("head", (205, 205, 205))
    face_color = palette.get("face", (145, 145, 145))
    front_arm_upper_color = palette.get("front_arm_upper", palette.get("front_arm", torso_color))
    front_arm_lower_color = palette.get("front_arm_lower", front_arm_upper_color)
    rear_arm_upper_color = palette.get("rear_arm_upper", palette.get("rear_arm", torso_color))
    rear_arm_lower_color = palette.get("rear_arm_lower", rear_arm_upper_color)
    front_leg_upper_color = palette.get("front_leg_upper", palette.get("leg", pelvis_color))
    front_leg_lower_color = palette.get("front_leg_lower", front_leg_upper_color)
    rear_leg_upper_color = palette.get("rear_leg_upper", palette.get("leg", pelvis_color))
    rear_leg_lower_color = palette.get("rear_leg_lower", rear_leg_upper_color)
    hand_color = palette.get("hands", face_color)
    foot_color = palette.get("feet", hand_color)
    hair_color = palette.get("hair", head_color)
    belt_color = palette.get("belt")
    base_torso_shift = palette.get("idle_shift", 0.0) * width * facing
    base_torso_tilt = palette.get("idle_tilt", 0.0) * facing

    bob = math.sin(t * IDLE_BOB_FREQUENCY) * IDLE_BOB_AMPLITUDE
    torso_shift_x = 0.0
    torso_tilt = 0.0
    stance_drop = 0.0
    shoulder_counter = 0.0
    front_stride = 0.0
    back_stride = 0.0
    front_lift = 0.0
    back_lift = 0.0
    front_hand = (0, 0)
    rear_hand = (0, 0)
    attack_extension = 0.0
    front_knee_extra_lift = 0.0
    rear_knee_extra_lift = 0.0

    if pose == "walk":
        stride_amp = width * (0.10 + move_ratio * 0.06)  # compact brawler steps (was 0.14+0.08)
        front_stride = walk_sin * stride_amp
        back_stride = walk_sin * stride_amp
        front_lift = max(0.0, walk_cos) * height * 0.12   # snappier knee lift
        back_lift = max(0.0, -walk_cos) * height * 0.12
        front_knee_extra_lift = front_lift * 0.50
        rear_knee_extra_lift = back_lift * 0.50
        shoulder_counter = -walk_sin * width * 0.07
        torso_shift_x = facing * width * (0.02 + move_ratio * 0.02)
        torso_tilt = (-0.04 - walk_sin * 0.02) * facing
        stance_drop = height * 0.04
        bob += math.sin(walk_phase * 2.0) * WALK_BOB_AMPLITUDE
    elif pose == "jump":
        bob -= JUMP_BOB_OFFSET
        torso_tilt = 0.06 * facing
        front_stride = width * 0.1
        back_stride = -width * 0.1
        front_lift = height * 0.24
        back_lift = height * 0.2
        stance_drop = height * 0.03
    elif pose == "attack":
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            # Load-up: torso winds back hard (classic arcade anticipation)
            torso_shift_x = -facing * width * (0.10 + 0.05 * phase)
            torso_tilt = (0.12 + 0.04 * phase) * facing
            front_stride = -width * 0.06
            back_stride = width * 0.20
            back_lift = height * 0.06
            stance_drop = height * 0.08
            attack_extension = 0.04
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            # Strike: torso twist + full arm extension
            torso_shift_x = facing * width * (0.06 + 0.20 * phase)
            torso_tilt = (-0.16 + 0.04 * phase) * facing
            front_stride = width * (0.14 + 0.12 * phase)
            back_stride = -width * (0.10 + 0.05 * phase)
            front_lift = height * 0.02
            back_lift = height * 0.04
            stance_drop = height * 0.09
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / (1.0 - strike_end)
            settle = 1.0 - phase
            torso_shift_x = facing * width * (0.18 * settle)
            torso_tilt = (-0.10 * settle) * facing
            front_stride = width * (0.16 * settle)
            back_stride = -width * (0.08 * settle)
            back_lift = height * 0.02 * settle
            stance_drop = height * 0.06 * settle
            attack_extension = max(0.0, 0.65 * settle)
    elif pose == "kick":
        # Secondary attack: heavy kick - front leg chambers then extends
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            # Chamber: knee pulls high and back – big, readable chamber
            torso_shift_x = -facing * width * (0.06 + 0.05 * phase)
            torso_tilt = (0.10 + 0.08 * phase) * facing
            front_stride = -width * (0.08 + 0.22 * phase)
            back_stride = width * 0.12
            front_lift = height * (0.12 + 0.32 * phase)
            stance_drop = height * 0.06
            attack_extension = 0.0
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            # Strike: leg shoots forward – very extended, torso leans back
            torso_shift_x = facing * width * (0.06 + 0.10 * phase)
            torso_tilt = (-0.14 + 0.03 * phase) * facing
            front_stride = width * (0.18 + 0.38 * phase)
            back_stride = -width * 0.08
            front_lift = height * (0.42 - 0.12 * phase)
            back_lift = height * 0.04
            stance_drop = height * 0.07
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / max(MIN_PHASE_DIVISOR, 1.0 - strike_end)
            settle = 1.0 - phase
            torso_shift_x = facing * width * 0.10 * settle
            torso_tilt = -0.12 * facing * settle
            front_stride = width * 0.28 * settle
            front_lift = height * 0.20 * settle
            back_stride = -width * 0.08 * settle
            stance_drop = height * 0.04 * settle
            attack_extension = 0.45 * settle
    elif pose == "hurt":
        snap = max(0.0, min(1.0, hurt_ratio))
        if hit_region == "head":
            # Dramatic snap-back: upper body thrown hard backward
            torso_shift_x = -facing * width * (0.44 * snap)
            torso_tilt = -facing * 0.60 * snap
            front_stride = -facing * width * 0.12
            back_stride = facing * width * 0.26
            front_lift = height * 0.08 * snap
            back_lift = height * 0.28 * snap
            stance_drop = height * 0.06 * snap
        elif hit_region == "legs":
            # Stumble: body drops, legs buckle
            torso_shift_x = -facing * width * (0.14 * snap)
            torso_tilt = -facing * 0.24 * snap
            front_stride = facing * width * 0.34 * snap
            back_stride = facing * width * 0.10
            front_lift = height * 0.28 * snap
            back_lift = height * 0.08 * snap
            stance_drop = height * 0.16 * snap
        else:
            # Torso: standard knock-back
            torso_shift_x = -facing * width * (0.30 * snap)
            torso_tilt = -facing * 0.42 * snap
            front_stride = -facing * width * 0.18
            back_stride = facing * width * 0.20
            front_lift = height * 0.12 * snap
            back_lift = height * 0.20 * snap
            stance_drop = height * 0.08 * snap
    elif pose == "knockdown":
        snap = max(0.0, min(1.0, hurt_ratio))
        # Dramatic collapse: near-horizontal body, legs fly outward
        torso_shift_x = -facing * width * (0.40 * snap)
        torso_tilt = -facing * 0.85 * snap
        front_stride = facing * width * 0.52 * snap
        back_stride = -facing * width * 0.24 * snap
        front_lift = height * 0.30 * snap
        back_lift = height * 0.10 * snap
        stance_drop = height * (0.18 + 0.14 * snap)
    elif pose == "aerial_attack":
        # Light aerial strike – arm extends forward, legs stay tucked in air
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        bob -= JUMP_BOB_OFFSET
        front_stride = width * 0.10
        back_stride = -width * 0.08
        front_lift = height * 0.22
        back_lift = height * 0.18
        stance_drop = height * 0.03
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            torso_shift_x = -facing * width * 0.04 * phase
            torso_tilt = 0.04 * facing * phase
            attack_extension = 0.02
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            torso_shift_x = facing * width * (0.06 + 0.16 * phase)
            torso_tilt = (-0.08 + 0.02 * phase) * facing
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / max(MIN_PHASE_DIVISOR, 1.0 - strike_end)
            settle = 1.0 - phase
            torso_shift_x = facing * width * 0.12 * settle
            torso_tilt = -0.06 * facing * settle
            attack_extension = 0.4 * settle
    elif pose == "aerial_kick":
        # Flying kick – body leans forward, front leg shoots out
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        bob -= JUMP_BOB_OFFSET
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            # Chamber: knee draws up and back
            torso_tilt = (0.08 + 0.06 * phase) * facing
            torso_shift_x = facing * width * 0.04 * phase
            front_stride = -width * (0.04 + 0.18 * phase)
            back_stride = -width * 0.08
            front_lift = height * (0.20 + 0.18 * phase)
            back_lift = height * 0.18
            stance_drop = height * 0.03
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            # Strike: leg shoots forward at body height
            torso_tilt = (0.12 - 0.08 * phase) * facing
            torso_shift_x = facing * width * (0.10 + 0.10 * phase)
            front_stride = width * (0.16 + 0.38 * phase)
            back_stride = -width * 0.10
            front_lift = height * (0.36 - 0.10 * phase)
            back_lift = height * 0.18
            stance_drop = height * 0.04
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / max(MIN_PHASE_DIVISOR, 1.0 - strike_end)
            settle = 1.0 - phase
            torso_tilt = 0.04 * facing * settle
            torso_shift_x = facing * width * 0.10 * settle
            front_stride = width * 0.28 * settle
            front_lift = height * 0.20 * settle
            back_stride = -width * 0.10 * settle
            back_lift = height * 0.16
            stance_drop = height * 0.03
            attack_extension = 0.3 * settle
    elif pose == "idle":
        # Classic brawler guard: compact stagger, deep crouch, fists at chest
        front_stride = width * 0.06
        back_stride = -width * 0.02
        stance_drop = height * IDLE_STANCE_DROP_RATIO
        torso_shift_x = base_torso_shift
        torso_tilt = -0.04 * facing
    elif pose == "crouch":
        # Deep fighting squat: compressed body, fists guarding low
        front_stride = width * 0.24
        back_stride = width * 0.10
        stance_drop = height * 0.44
        torso_shift_x = base_torso_shift
        torso_tilt = 0.06 * facing
    elif pose == "crouch_punch":
        # Crouching punch: low stance, front arm thrusts forward
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        front_stride = width * 0.22
        back_stride = width * 0.08
        stance_drop = height * 0.42
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            torso_shift_x = -facing * width * 0.04 * phase
            torso_tilt = 0.08 * facing
            attack_extension = 0.02
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            torso_shift_x = facing * width * (0.04 + 0.18 * phase)
            torso_tilt = (-0.06 + 0.02 * phase) * facing
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / max(MIN_PHASE_DIVISOR, 1.0 - strike_end)
            settle = 1.0 - phase
            torso_shift_x = facing * width * 0.14 * settle
            torso_tilt = -0.04 * facing * settle
            attack_extension = 0.4 * settle
    elif pose == "crouch_kick":
        # Low sweeping kick: body stays low, front leg shoots out near ground
        anticipation_end = _clamp(
            attack_anticipation_end,
            MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_ANTICIPATION_END,
        )
        strike_end = _clamp(
            attack_strike_end,
            anticipation_end + MIN_ATTACK_PHASE_DURATION,
            MAX_ATTACK_STRIKE_END,
        )
        if clamped_attack_ratio < anticipation_end:
            phase = clamped_attack_ratio / anticipation_end
            front_stride = -width * (0.06 + 0.14 * phase)
            back_stride = width * 0.16
            front_lift = height * 0.04 * phase
            stance_drop = height * (0.38 + 0.06 * phase)
            torso_tilt = 0.06 * facing
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            # Leg sweeps out low, barely off the ground
            front_stride = width * (0.18 + 0.38 * phase)
            back_stride = -width * 0.06
            front_lift = height * 0.04
            torso_shift_x = facing * width * 0.06 * phase
            torso_tilt = 0.04 * facing
            stance_drop = height * 0.44
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / max(MIN_PHASE_DIVISOR, 1.0 - strike_end)
            settle = 1.0 - phase
            front_stride = width * 0.30 * settle
            back_stride = -width * 0.04 * settle
            front_lift = height * 0.03 * settle
            stance_drop = height * (0.38 + 0.06 * settle)
            torso_shift_x = facing * width * 0.04 * settle
            attack_extension = 0.3 * settle
    torso_tilt += base_torso_tilt

    torso_center_x = center_x + torso_shift_x
    head_center = (int(center_x + torso_shift_x * 0.18), int(top_y + head_radius + 2 + bob))

    shoulder_y = int(head_center[1] + head_radius + 4 + stance_drop * 0.35)
    left_shoulder = (
        int(torso_center_x - shoulder_span - shoulder_counter * 0.4),
        int(shoulder_y - torso_tilt * width * 0.8),
    )
    right_shoulder = (
        int(torso_center_x + shoulder_span - shoulder_counter * 0.4),
        int(shoulder_y + torso_tilt * width * 0.8),
    )

    hip_y = int(shoulder_y + torso_len + stance_drop * 0.65)
    left_hip = (
        int(torso_center_x - hip_span),
        int(hip_y + torso_tilt * width * 0.5),
    )
    right_hip = (
        int(torso_center_x + hip_span),
        int(hip_y - torso_tilt * width * 0.5),
    )

    # Waist sits ~55% down the torso, narrower than both shoulders and hips.
    waist_y = int(shoulder_y + (hip_y - shoulder_y) * WAIST_POSITION_RATIO)
    waist_left = (
        int(torso_center_x - waist_span),
        int(waist_y + torso_tilt * width * WAIST_TILT_FACTOR),
    )
    waist_right = (
        int(torso_center_x + waist_span),
        int(waist_y - torso_tilt * width * WAIST_TILT_FACTOR),
    )

    chest_points = [
        left_shoulder,
        right_shoulder,
        waist_right,
        waist_left,
    ]
    pelvis_points = [
        waist_left,
        waist_right,
        right_hip,
        left_hip,
    ]

    # Blocky 8-bit brawler head – squarer silhouette
    head_poly = [
        (int(head_center[0] - head_radius * 0.54), int(head_center[1] - head_radius * 0.90)),
        (int(head_center[0] + head_radius * 0.54), int(head_center[1] - head_radius * 0.90)),
        (int(head_center[0] + head_radius * 0.94), int(head_center[1] - head_radius * 0.28)),
        (int(head_center[0] + head_radius * 0.90), int(head_center[1] + head_radius * 0.62)),
        (int(head_center[0] + head_radius * 0.30), int(head_center[1] + head_radius * 1.00)),
        (int(head_center[0] - head_radius * 0.30), int(head_center[1] + head_radius * 1.00)),
        (int(head_center[0] - head_radius * 0.90), int(head_center[1] + head_radius * 0.62)),
        (int(head_center[0] - head_radius * 0.94), int(head_center[1] - head_radius * 0.28)),
    ]
    # Large swept-back hair mass – Double Dragon Billy style, tall and prominent
    hair_poly = [
        (int(head_center[0] - head_radius * 0.54), int(head_center[1] - head_radius * 0.90)),
        (int(head_center[0] + head_radius * 0.54), int(head_center[1] - head_radius * 0.90)),
        (int(head_center[0] + head_radius * 0.86), int(head_center[1] - head_radius * 1.18)),
        (int(head_center[0] + head_radius * 0.62), int(head_center[1] - head_radius * 1.84)),
        (int(head_center[0] + head_radius * 0.20), int(head_center[1] - head_radius * 2.10)),
        (int(head_center[0] - head_radius * 0.16), int(head_center[1] - head_radius * 1.92)),
        (int(head_center[0] - head_radius * 0.56), int(head_center[1] - head_radius * 1.38)),
    ]

    # ── Face features (all on the forward-facing side) ──────────────────────────
    eye_x = int(head_center[0] + facing * head_radius * 0.44)
    eye_y = int(head_center[1] - head_radius * 0.18)
    eye_w = max(3, int(head_radius * 0.52))
    eye_h = max(2, int(head_radius * 0.34))
    brow_y = int(eye_y - eye_h * 1.0)
    brow_x0 = int(eye_x - eye_w * 0.55)
    brow_x1 = int(eye_x + eye_w * 0.55)
    nose_x = int(head_center[0] + facing * head_radius * 0.86)
    nose_y = int(head_center[1] + head_radius * 0.06)
    nose_r = max(1, int(head_radius * 0.14))
    mouth_y = int(head_center[1] + head_radius * 0.46)
    mouth_x0 = int(head_center[0] + facing * head_radius * 0.36)
    mouth_x1 = int(head_center[0] + facing * head_radius * 0.72)

    front_shoulder = right_shoulder if facing > 0 else left_shoulder
    rear_shoulder = left_shoulder if facing > 0 else right_shoulder
    front_hip = right_hip if facing > 0 else left_hip
    rear_hip = left_hip if facing > 0 else right_hip

    if pose == "attack":
        attack_reach = width * (
            ATTACK_BASE_REACH + ATTACK_REACH_EXTENSION * attack_extension
        )
        front_hand = (
            int(front_shoulder[0] + facing * attack_reach),
            int(front_shoulder[1] + height * (0.05 - attack_extension * 0.04)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * (0.22 + attack_extension * 0.05)),
            int(rear_shoulder[1] + height * (0.2 + attack_extension * 0.04)),
        )
    elif pose == "jump":
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.15),
            int(front_shoulder[1] + height * 0.14),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.1),
            int(rear_shoulder[1] + height * 0.15),
        )
    elif pose == "hurt":
        if hit_region == "head":
            # Arms flung back from impact
            front_hand = (
                int(front_shoulder[0] - facing * width * 0.28),
                int(front_shoulder[1] + height * 0.18),
            )
            rear_hand = (
                int(rear_shoulder[0] - facing * width * 0.20),
                int(rear_shoulder[1] + height * 0.16),
            )
        elif hit_region == "legs":
            # Arms reach down for balance
            front_hand = (
                int(front_shoulder[0] + facing * width * 0.06),
                int(front_shoulder[1] + height * 0.30),
            )
            rear_hand = (
                int(rear_shoulder[0] - facing * width * 0.08),
                int(rear_shoulder[1] + height * 0.28),
            )
        else:
            # Standard torso hurt: arms pulled back
            front_hand = (
                int(front_shoulder[0] - facing * width * 0.18),
                int(front_shoulder[1] + height * 0.16),
            )
            rear_hand = (
                int(rear_shoulder[0] - facing * width * 0.24),
                int(rear_shoulder[1] + height * 0.18),
            )
    elif pose == "knockdown":
        # Arms splayed out during collapse
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.24),
            int(front_shoulder[1] + height * 0.32),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.10),
            int(rear_shoulder[1] + height * 0.34),
        )
    elif pose == "kick":
        # Arms in guard/balance position while leg kicks
        arm_guard = min(1.0, clamped_attack_ratio / max(0.01, attack_anticipation_end))
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.08),
            int(front_shoulder[1] + height * (0.20 + 0.06 * arm_guard)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.04),
            int(rear_shoulder[1] + height * 0.17),
        )
    elif pose == "aerial_attack":
        # Front arm extends forward like a jab; rear arm guards
        attack_reach = width * (ATTACK_BASE_REACH + ATTACK_REACH_EXTENSION * attack_extension)
        front_hand = (
            int(front_shoulder[0] + facing * attack_reach),
            int(front_shoulder[1] + height * (0.06 - attack_extension * 0.04)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.16),
            int(rear_shoulder[1] + height * 0.18),
        )
    elif pose == "aerial_kick":
        # Arms sweep back for aerodynamics during flying kick
        kick_phase = min(1.0, clamped_attack_ratio / max(MIN_PHASE_DIVISOR, attack_anticipation_end))
        front_hand = (
            int(front_shoulder[0] - facing * width * (0.04 + 0.08 * kick_phase)),
            int(front_shoulder[1] + height * (0.16 + 0.06 * kick_phase)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.18),
            int(rear_shoulder[1] + height * 0.14),
        )
    elif pose == "idle":
        # Classic guard: BOTH fists forward at chin/chest – not one arm behind
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.10),
            int(front_shoulder[1] + height * 0.07),
        )
        rear_hand = (
            int(rear_shoulder[0] + facing * width * 0.06),  # forward, not backward
            int(rear_shoulder[1] + height * 0.06),
        )
    elif pose == "crouch":
        # Crouching guard: both fists forward and compact at gut level
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.16),
            int(front_shoulder[1] + height * 0.22),
        )
        rear_hand = (
            int(rear_shoulder[0] + facing * width * 0.08),  # forward, not backward
            int(rear_shoulder[1] + height * 0.20),
        )
    elif pose == "crouch_punch":
        # Front arm extends forward at gut level; rear arm guards near chin
        attack_reach = width * (ATTACK_BASE_REACH + ATTACK_REACH_EXTENSION * attack_extension)
        front_hand = (
            int(front_shoulder[0] + facing * attack_reach),
            int(front_shoulder[1] + height * (0.22 - attack_extension * 0.06)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.16),
            int(rear_shoulder[1] + height * 0.22),
        )
    elif pose == "crouch_kick":
        # Arms balanced at chest while front leg sweeps out
        arm_guard = min(1.0, clamped_attack_ratio / max(0.01, attack_anticipation_end))
        front_hand = (
            int(front_shoulder[0] + facing * width * 0.12),
            int(front_shoulder[1] + height * (0.20 + 0.06 * arm_guard)),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.04),
            int(rear_shoulder[1] + height * 0.18),
        )
    elif pose == "walk":
        # Brawler walk: arms swing forward from the chest, not hanging at hip level
        arm_swing = walk_sin * width * (0.10 + move_ratio * 0.06)
        # Front arm pumps forward-back relative to shoulder position
        front_hand = (
            int(front_shoulder[0] + facing * (width * 0.08 - arm_swing * 0.80)),
            int(front_shoulder[1] + height * (0.18 + 0.06 * abs(walk_sin))),
        )
        # Rear arm swings in opposite phase, also staying in front
        rear_hand = (
            int(rear_shoulder[0] + facing * (width * 0.06 + arm_swing * 0.60)),
            int(rear_shoulder[1] + height * 0.18),
        )

    # Pose-specific elbow bend: guard poses have more compact tuck
    if pose in ("idle", "walk"):
        front_elbow = _joint_midpoint(front_shoulder, front_hand, height * 0.04, facing * width * 0.04)
        rear_elbow = _joint_midpoint(rear_shoulder, rear_hand, height * 0.04, -facing * width * 0.04)
    else:
        front_elbow = _joint_midpoint(front_shoulder, front_hand, height * 0.08, facing * width * 0.08)
        rear_elbow = _joint_midpoint(rear_shoulder, rear_hand, height * 0.08, -facing * width * 0.08)

    base_foot_separation = width * 0.10
    front_foot = (
        int(center_x + facing * (base_foot_separation + front_stride)),
        int(bottom_y - front_lift),
    )
    rear_foot = (
        int(center_x - facing * (base_foot_separation + back_stride)),
        int(bottom_y - back_lift),
    )
    if pose == "jump":
        front_foot = (
            int(center_x + facing * width * 0.16),
            int(bottom_y - height * 0.2),
        )
        rear_foot = (
            int(center_x - facing * width * 0.16),
            int(bottom_y - height * 0.18),
        )

    front_knee = _joint_midpoint(front_hip, front_foot, height * 0.13 + front_knee_extra_lift, facing * width * 0.05)
    rear_knee = _joint_midpoint(rear_hip, rear_foot, height * 0.12 + rear_knee_extra_lift, -facing * width * 0.05)

    # Rear limbs (layered behind torso)
    _draw_bent_limb(
        screen,
        rear_leg_upper_color,
        rear_leg_lower_color,
        rear_hip,
        rear_knee,
        rear_foot,
        upper_leg_width,
        lower_leg_width,
    )
    _draw_bent_limb(
        screen,
        rear_arm_upper_color,
        rear_arm_lower_color,
        rear_shoulder,
        rear_elbow,
        rear_hand,
        upper_arm_width,
        lower_arm_width,
    )

    # Torso and head
    pygame.draw.polygon(screen, chest_color, chest_points)
    pygame.draw.polygon(screen, pelvis_color, pelvis_points)
    if belt_color is not None:
        # Belt sits just below the waist, bridging toward the hips.
        belt_bottom_left = _point_lerp(waist_left, left_hip, BELT_DROP_RATIO)
        belt_bottom_right = _point_lerp(waist_right, right_hip, BELT_DROP_RATIO)
        pygame.draw.polygon(
            screen,
            belt_color,
            [waist_left, waist_right, belt_bottom_right, belt_bottom_left],
        )
    if torso_color != chest_color:
        torso_overlay = [
            _point_lerp(left_shoulder, right_shoulder, 0.18),
            _point_lerp(left_shoulder, right_shoulder, 0.82),
            _point_lerp(waist_right, waist_left, 0.82),
            _point_lerp(waist_right, waist_left, 0.18),
        ]
        pygame.draw.polygon(screen, torso_color, torso_overlay)

    # Chest highlight strip – adds brawny mass to the pec area
    chest_hi = (
        min(255, chest_color[0] + 28),
        min(255, chest_color[1] + 22),
        min(255, chest_color[2] + 18),
    )
    chest_hi_pts = [
        _point_lerp(left_shoulder, right_shoulder, 0.30),
        _point_lerp(left_shoulder, right_shoulder, 0.70),
        _point_lerp(waist_right, waist_left, 0.68),
        _point_lerp(waist_right, waist_left, 0.32),
    ]
    pygame.draw.polygon(screen, chest_hi, chest_hi_pts)

    # Collar: simple dark V neckline
    collar_top_y = shoulder_y + max(1, int((hip_y - shoulder_y) * 0.04))
    collar_v_tip = (int(torso_center_x), int(shoulder_y + torso_len * 0.38))
    collar_left_pt = (int(torso_center_x - shoulder_span * 0.28), collar_top_y)
    collar_right_pt = (int(torso_center_x + shoulder_span * 0.28), collar_top_y)
    collar_col = (
        max(0, chest_color[0] - 50),
        max(0, chest_color[1] - 50),
        max(0, chest_color[2] - 50),
    )
    collar_w = max(1, upper_arm_width // 3)
    pygame.draw.line(screen, collar_col, collar_left_pt, collar_v_tip, collar_w)
    pygame.draw.line(screen, collar_col, collar_right_pt, collar_v_tip, collar_w)

    # Neck
    neck_w = max(3, int(width * NECK_WIDTH_RATIO))
    neck_poly = [
        (int(head_center[0] - neck_w), int(head_center[1] + head_radius * 0.68)),
        (int(head_center[0] + neck_w), int(head_center[1] + head_radius * 0.68)),
        (int(torso_center_x + neck_w + 1), shoulder_y),
        (int(torso_center_x - neck_w - 1), shoulder_y),
    ]
    pygame.draw.polygon(screen, head_color, neck_poly)

    pygame.draw.polygon(screen, head_color, head_poly)
    if hair_color != head_color:
        pygame.draw.polygon(screen, hair_color, hair_poly)

    # Eye: white sclera + dark iris/pupil
    pygame.draw.ellipse(screen, EYE_SCLERA_COLOR, (eye_x - eye_w // 2, eye_y - eye_h // 2, eye_w, eye_h))
    pupil_w = max(2, eye_w // 2)
    pupil_h = max(2, eye_h // 2)
    pygame.draw.ellipse(screen, EYE_IRIS_COLOR, (eye_x - pupil_w // 2, eye_y - pupil_h // 2, pupil_w, pupil_h))

    # Eyebrow: uses hair colour, slight inward angle
    brow_w = max(1, head_radius // 6)
    pygame.draw.line(screen, hair_color, (brow_x0, brow_y), (brow_x1, brow_y - 1), brow_w)

    # Nose: small dark dot at the forward edge
    nose_dark = (max(0, face_color[0] - NOSE_DARKEN_AMOUNT), max(0, face_color[1] - NOSE_DARKEN_AMOUNT), max(0, face_color[2] - NOSE_DARKEN_AMOUNT))
    pygame.draw.circle(screen, nose_dark, (nose_x, nose_y), nose_r)

    # Mouth: short horizontal line
    mouth_dark = (max(0, face_color[0] - MOUTH_DARKEN_AMOUNT), max(0, face_color[1] - MOUTH_DARKEN_AMOUNT), max(0, face_color[2] - MOUTH_DARKEN_AMOUNT))
    mouth_w = max(1, head_radius // 7)
    pygame.draw.line(screen, mouth_dark, (mouth_x0, mouth_y), (mouth_x1, mouth_y), mouth_w)

    # Front limbs (layered in front)
    _draw_bent_limb(
        screen,
        front_leg_upper_color,
        front_leg_lower_color,
        front_hip,
        front_knee,
        front_foot,
        upper_leg_width,
        lower_leg_width,
    )
    _draw_bent_limb(
        screen,
        front_arm_upper_color,
        front_arm_lower_color,
        front_shoulder,
        front_elbow,
        front_hand,
        upper_arm_width,
        lower_arm_width,
    )

    hand_w = max(MIN_HAND_RADIUS * 2, int(width * HAND_SIZE_RATIO * FIST_WIDTH_MULTIPLIER))
    hand_h = max(MIN_HAND_RADIUS, int(hand_w * 0.72))
    rear_fist_rect = pygame.Rect(rear_hand[0] - hand_w // 2, rear_hand[1] - hand_h // 2, hand_w, hand_h)
    front_fist_rect = pygame.Rect(front_hand[0] - hand_w // 2, front_hand[1] - hand_h // 2, hand_w, hand_h)
    pygame.draw.rect(screen, hand_color, rear_fist_rect, border_radius=2)
    pygame.draw.rect(screen, hand_color, front_fist_rect, border_radius=2)

    # Draw carried weapon extending from front hand
    if weapon_name is not None:
        _draw_weapon_at_hand(screen, weapon_name, front_hand, facing, width, height, attack_extension)

    foot_len = max(MIN_FOOT_LENGTH, int(width * FOOT_LENGTH_RATIO))
    foot_height = max(MIN_FOOT_HEIGHT, int(height * FOOT_HEIGHT_RATIO))
    rear_foot_poly = [
        (int(rear_foot[0] - facing * foot_len * 0.22), int(rear_foot[1])),
        (int(rear_foot[0] + facing * foot_len * 0.88), int(rear_foot[1])),
        (int(rear_foot[0] + facing * foot_len), int(rear_foot[1] + foot_height * 0.52)),
        (int(rear_foot[0] + facing * foot_len * 0.84), int(rear_foot[1] + foot_height)),
        (int(rear_foot[0] - facing * foot_len * 0.28), int(rear_foot[1] + foot_height)),
    ]
    front_foot_poly = [
        (int(front_foot[0] - facing * foot_len * 0.22), int(front_foot[1])),
        (int(front_foot[0] + facing * foot_len * 0.88), int(front_foot[1])),
        (int(front_foot[0] + facing * foot_len), int(front_foot[1] + foot_height * 0.52)),
        (int(front_foot[0] + facing * foot_len * 0.84), int(front_foot[1] + foot_height)),
        (int(front_foot[0] - facing * foot_len * 0.28), int(front_foot[1] + foot_height)),
    ]
    pygame.draw.polygon(screen, foot_color, rear_foot_poly)
    pygame.draw.polygon(screen, foot_color, front_foot_poly)

    # ── Gauntlet-style archetype overlays ──────────────────────────────────────
    _archetype = palette.get("archetype")
    if _archetype == "warrior":
        _draw_archetype_warrior(
            screen, palette, head_center, head_radius,
            waist_left, waist_right, left_hip, right_hip,
            bottom_y, hip_y, upper_leg_width,
        )
    elif _archetype == "valkyrie":
        _draw_archetype_valkyrie(
            screen, palette, head_center, head_radius, facing,
            rear_shoulder, rear_hip,
        )
    elif _archetype == "wizard":
        _draw_archetype_wizard(
            screen, palette, head_center, head_radius, facing,
            left_hip, right_hip, hip_y, bottom_y,
        )
    elif _archetype == "elf":
        _draw_archetype_elf(
            screen, palette, head_center, head_radius, facing,
            rear_shoulder, rear_hip,
        )
