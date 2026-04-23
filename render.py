import math

import pygame

BASE_WALK_PHASE_SPEED = 4.2
WALK_PHASE_SPEED_FROM_MOVE = 4.0
IDLE_BOB_FREQUENCY = 2.2
IDLE_BOB_AMPLITUDE = 1.4
ATTACK_BASE_REACH = 0.28
ATTACK_REACH_EXTENSION = 0.9
ATTACK_ANTICIPATION_END = 0.34
ATTACK_STRIKE_END = 0.62
MIN_ATTACK_PHASE_DURATION = 0.05
MAX_ATTACK_ANTICIPATION_END = 0.9
MAX_ATTACK_STRIKE_END = 0.95
JUMP_BOB_OFFSET = 4.0
SHOULDER_SPAN_RATIO = 0.24
HIP_SPAN_RATIO = 0.2
SHADOW_DEPTH_BASE_SCALE = 0.82
SHADOW_DEPTH_SCALE_RANGE = 0.35


def _joint_midpoint(a, b, lift, bend):
    return (
        int((a[0] + b[0]) * 0.5 + bend),
        int((a[1] + b[1]) * 0.5 - lift),
    )


def _draw_limb(screen, color, start, mid, end, width):
    pygame.draw.line(screen, color, start, mid, width)
    pygame.draw.line(screen, color, mid, end, width)


def get_depth_scale(ground_y, lane_min, lane_max):
    if lane_max <= lane_min:
        return SHADOW_DEPTH_BASE_SCALE
    lane_ratio = (ground_y - lane_min) / (lane_max - lane_min)
    lane_ratio = max(0.0, min(1.0, lane_ratio))
    return SHADOW_DEPTH_BASE_SCALE + lane_ratio * SHADOW_DEPTH_SCALE_RANGE


def _clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


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
):
    facing = 1 if facing >= 0 else -1
    clamped_attack_ratio = max(0.0, min(1.0, attack_ratio))
    t = pygame.time.get_ticks() / 1000.0 + phase_offset
    walk_phase = t * (BASE_WALK_PHASE_SPEED + move_ratio * WALK_PHASE_SPEED_FROM_MOVE)
    walk_sin = math.sin(walk_phase)

    width = body_rect.width
    height = body_rect.height
    center_x = body_rect.centerx
    top_y = body_rect.top
    bottom_y = body_rect.bottom

    head_radius = max(6, int(width * 0.2))
    shoulder_span = int(width * SHOULDER_SPAN_RATIO)
    hip_span = int(width * HIP_SPAN_RATIO)
    torso_len = int(height * 0.3)

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

    if pose == "walk":
        stride = walk_sin * (0.36 + move_ratio * 0.18)
        front_stride = stride * width
        back_stride = -stride * width * 0.92
        front_lift = max(0.0, -walk_sin) * height * 0.17
        back_lift = max(0.0, walk_sin) * height * 0.17
        shoulder_counter = -walk_sin * width * 0.11
        torso_shift_x = facing * width * (0.04 + move_ratio * 0.02)
        torso_tilt = (-0.08 - walk_sin * 0.03) * facing
        stance_drop = height * 0.04
        bob += math.sin(walk_phase * 2.0) * 0.8
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
            torso_shift_x = -facing * width * (0.08 + 0.05 * phase)
            torso_tilt = (0.1 + 0.03 * phase) * facing
            front_stride = -width * 0.04
            back_stride = width * 0.16
            back_lift = height * 0.06
            stance_drop = height * 0.05
            attack_extension = 0.04
        elif clamped_attack_ratio < strike_end:
            phase = (clamped_attack_ratio - anticipation_end) / (strike_end - anticipation_end)
            torso_shift_x = facing * width * (0.06 + 0.24 * phase)
            torso_tilt = (-0.14 + 0.03 * phase) * facing
            front_stride = width * (0.14 + 0.1 * phase)
            back_stride = -width * (0.1 + 0.05 * phase)
            front_lift = height * 0.02
            back_lift = height * 0.04
            stance_drop = height * 0.07
            attack_extension = phase
        else:
            phase = (clamped_attack_ratio - strike_end) / (1.0 - strike_end)
            settle = 1.0 - phase
            torso_shift_x = facing * width * (0.18 * settle)
            torso_tilt = (-0.09 * settle) * facing
            front_stride = width * (0.16 * settle)
            back_stride = -width * (0.08 * settle)
            back_lift = height * 0.02 * settle
            stance_drop = height * 0.04 * settle
            attack_extension = max(0.0, 0.6 * settle)
    elif pose == "hurt":
        snap = max(0.0, min(1.0, hurt_ratio))
        torso_shift_x = -facing * width * (0.24 * snap)
        torso_tilt = -facing * 0.34 * snap
        front_stride = -facing * width * 0.15
        back_stride = facing * width * 0.16
        front_lift = height * 0.1 * snap
        back_lift = height * 0.16 * snap
        stance_drop = height * 0.06 * snap

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

    torso_points = [left_shoulder, right_shoulder, right_hip, left_hip]
    pygame.draw.polygon(screen, palette["torso"], torso_points)
    pygame.draw.circle(screen, palette["head"], head_center, head_radius)

    face_tip_x = int(head_center[0] + facing * (head_radius + 2))
    pygame.draw.polygon(
        screen,
        palette["face"],
        [
            (face_tip_x, head_center[1]),
            (int(head_center[0] + facing * (head_radius - 2)), head_center[1] - 3),
            (int(head_center[0] + facing * (head_radius - 2)), head_center[1] + 3),
        ],
    )

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
        front_hand = (
            int(front_shoulder[0] - facing * width * 0.18),
            int(front_shoulder[1] + height * 0.16),
        )
        rear_hand = (
            int(rear_shoulder[0] - facing * width * 0.24),
            int(rear_shoulder[1] + height * 0.18),
        )
    else:
        arm_swing = walk_sin * width * 0.2 * (0.2 + move_ratio * 0.8)
        front_hand = (
            int(front_shoulder[0] - facing * (width * (0.16 + 0.05 * move_ratio) + arm_swing)),
            int(front_shoulder[1] + height * (0.18 + 0.03 * abs(walk_sin))),
        )
        rear_hand = (
            int(rear_shoulder[0] + facing * (width * (0.08 + 0.05 * move_ratio) + arm_swing * 0.8)),
            int(rear_shoulder[1] + height * 0.24),
        )

    front_elbow = _joint_midpoint(front_shoulder, front_hand, height * 0.08, facing * width * 0.05)
    rear_elbow = _joint_midpoint(rear_shoulder, rear_hand, height * 0.08, -facing * width * 0.05)
    _draw_limb(screen, palette["front_arm"], front_shoulder, front_elbow, front_hand, 3)
    _draw_limb(screen, palette["rear_arm"], rear_shoulder, rear_elbow, rear_hand, 3)

    base_foot_separation = width * 0.24
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

    front_knee = _joint_midpoint(front_hip, front_foot, height * 0.11, facing * width * 0.06)
    rear_knee = _joint_midpoint(rear_hip, rear_foot, height * 0.1, -facing * width * 0.05)
    _draw_limb(screen, palette["leg"], front_hip, front_knee, front_foot, 4)
    _draw_limb(screen, palette["leg"], rear_hip, rear_knee, rear_foot, 4)
