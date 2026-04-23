import pygame

LANE_CHASE_THRESHOLD = 4
LANE_CHASE_SPEED = 1.5
SHADOW_BASE_SCALE = 0.9
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0

class Enemy:
    def __init__(self, x, y, screen_width, screen_height):
        self.x = float(x)
        self.y = float(y)
        self.width = 36
        self.height = 72
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 3
        self.gravity = 0.8
        self.on_ground = True
        self.health = 100
        self.hit_stun_timer = 0
        self.hurt_flash_timer = 0
        self.last_hit_attack_id = -1
        self.defeat_handled = False
        self.facing = -1

    def update(self, player):
        if self.hurt_flash_timer > 0:
            self.hurt_flash_timer -= 1

        if self.health <= 0:
            return

        if self.hit_stun_timer > 0:
            self.hit_stun_timer -= 1
            self.vel_x = 0
        else:
            if player.x > self.x + 4:
                self.vel_x = self.speed
            elif player.x < self.x - 4:
                self.vel_x = -self.speed
            else:
                self.vel_x = 0

            if player.ground_y > self.ground_y + LANE_CHASE_THRESHOLD:
                self.ground_y += LANE_CHASE_SPEED
            elif player.ground_y < self.ground_y - LANE_CHASE_THRESHOLD:
                self.ground_y -= LANE_CHASE_SPEED

        if self.vel_x > 0:
            self.facing = 1
        elif self.vel_x < 0:
            self.facing = -1

        self.vel_y += self.gravity
        self.x += self.vel_x
        self.y += self.vel_y

        self.x = max(0, min(self.x, self.screen_width - self.width))
        lane_min = self.screen_height * 0.5
        lane_max = self.screen_height - self.height - 20
        self.ground_y = max(lane_min, min(self.ground_y, lane_max))
        if self.y >= self.ground_y:
            self.y = self.ground_y
            self.vel_y = 0.0
            self.on_ground = True

    def get_rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def draw(self, screen):
        shadow_scale = SHADOW_BASE_SCALE - min(
            SHADOW_MAX_REDUCTION,
            max(0.0, (self.ground_y - self.y) / SHADOW_JUMP_DIVISOR),
        )
        shadow_width = int(self.width * shadow_scale)
        shadow_width = max(10, shadow_width)
        shadow_height = max(4, int(shadow_width * 0.35))
        shadow_rect = pygame.Rect(
            int(self.x + self.width / 2 - shadow_width / 2),
            int(self.ground_y + self.height + 3 - shadow_height / 2),
            shadow_width,
            shadow_height,
        )
        pygame.draw.ellipse(screen, (35, 35, 35), shadow_rect)

        body_color = (220, 220, 220) if self.hurt_flash_timer > 0 else (100, 100, 100)
        body_rect = self.get_rect()
        center_x = body_rect.centerx
        top_y = body_rect.top
        bottom_y = body_rect.bottom
        width = body_rect.width
        height = body_rect.height

        head_radius = max(6, int(width * 0.2))
        head_center = (center_x, top_y + head_radius + 2)
        shoulder_y = head_center[1] + head_radius + 4
        hip_y = top_y + int(height * 0.58)
        left_shoulder_x = center_x - int(width * 0.2)
        right_shoulder_x = center_x + int(width * 0.2)

        torso_points = [
            (left_shoulder_x, shoulder_y),
            (right_shoulder_x, shoulder_y),
            (center_x + int(width * 0.3), hip_y),
            (center_x - int(width * 0.3), hip_y),
        ]
        pygame.draw.polygon(screen, body_color, torso_points)
        pygame.draw.circle(screen, body_color, head_center, head_radius)

        face_tip_x = head_center[0] + self.facing * (head_radius + 2)
        face_mid_y = head_center[1]
        pygame.draw.polygon(
            screen,
            (40, 40, 40),
            [
                (face_tip_x, face_mid_y),
                (head_center[0] + self.facing * (head_radius - 2), face_mid_y - 3),
                (head_center[0] + self.facing * (head_radius - 2), face_mid_y + 3),
            ],
        )

        arm_reach_x = center_x + self.facing * int(width * 0.6)
        arm_reach_y = shoulder_y + int(height * 0.07)
        rear_arm_x = center_x - self.facing * int(width * 0.5)
        rear_arm_y = shoulder_y + int(height * 0.11)
        forward_shoulder_x = right_shoulder_x if self.facing > 0 else left_shoulder_x
        rear_shoulder_x = left_shoulder_x if self.facing > 0 else right_shoulder_x
        pygame.draw.line(screen, (70, 70, 70), (forward_shoulder_x, shoulder_y), (arm_reach_x, arm_reach_y), 3)
        pygame.draw.line(screen, (60, 60, 60), (rear_shoulder_x, shoulder_y), (rear_arm_x, rear_arm_y), 3)

        left_hip = (center_x - int(width * 0.16), hip_y)
        right_hip = (center_x + int(width * 0.16), hip_y)
        left_foot = (center_x - int(width * 0.3), bottom_y)
        right_foot = (center_x + int(width * 0.3), bottom_y)
        pygame.draw.line(screen, (65, 65, 65), left_hip, left_foot, 4)
        pygame.draw.line(screen, (65, 65, 65), right_hip, right_foot, 4)

        pygame.draw.line(
            screen,
            (20, 20, 20),
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )
