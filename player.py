import pygame

SHADOW_BASE_SCALE = 0.9
SHADOW_MAX_REDUCTION = 0.5
SHADOW_JUMP_DIVISOR = 120.0


class Player:
    def __init__(self, x, y, screen_width, screen_height):
        self.x = float(x)
        self.y = float(y)
        self.width = 36
        self.height = 72
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_y = screen_height - self.height - 40
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 4
        self.lane_speed = 3
        self.jump_power = -15.0
        self.gravity = 0.8
        self.on_ground = True
        self.attack = False
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.attack_cooldown_frames = 18
        self.attack_duration_frames = 8
        self.prev_attack_pressed = False
        self.attack_id = 0
        self.facing = 1
        self.health = 100

    def update(self):
        keys = pygame.key.get_pressed()
        self.vel_x = 0.0
        lane_delta = 0.0
        if keys[pygame.K_LEFT]:
            self.vel_x = -self.speed
            self.facing = -1
        elif keys[pygame.K_RIGHT]:
            self.vel_x = self.speed
            self.facing = 1
        if self.on_ground:
            if keys[pygame.K_UP]:
                lane_delta -= self.lane_speed
            elif keys[pygame.K_DOWN]:
                lane_delta += self.lane_speed

        if keys[pygame.K_SPACE] and self.on_ground:
            self.vel_y = self.jump_power
            self.on_ground = False

        attack_pressed = keys[pygame.K_z]
        if attack_pressed and not self.prev_attack_pressed and self.attack_cooldown_timer <= 0:
            self.attack_timer = self.attack_duration_frames
            self.attack_cooldown_timer = self.attack_cooldown_frames
            self.attack_id += 1
        self.prev_attack_pressed = attack_pressed

        if self.attack_timer > 0:
            self.attack_timer -= 1
        self.attack = self.attack_timer > 0

        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= 1

        self.vel_y += self.gravity
        self.x += self.vel_x
        self.ground_y += lane_delta
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

    def get_attack_rect(self):
        if self.attack_timer <= 0:
            return None
        attack_width = 24
        attack_height = 18
        if self.facing > 0:
            attack_x = int(self.x + self.width + 2)
        else:
            attack_x = int(self.x - attack_width - 2)
        return pygame.Rect(
            attack_x,
            int(self.y + self.height // 3),
            attack_width,
            attack_height,
        )

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
        pygame.draw.ellipse(screen, (45, 45, 45), shadow_rect)

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
        pygame.draw.polygon(screen, (172, 172, 172), torso_points)
        pygame.draw.circle(screen, (205, 205, 205), head_center, head_radius)

        face_tip_x = head_center[0] + self.facing * (head_radius + 2)
        face_mid_y = head_center[1]
        pygame.draw.polygon(
            screen,
            (145, 145, 145),
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
        pygame.draw.line(screen, (160, 160, 160), (left_shoulder_x, shoulder_y), (arm_reach_x, arm_reach_y), 3)
        pygame.draw.line(screen, (152, 152, 152), (right_shoulder_x, shoulder_y), (rear_arm_x, rear_arm_y), 3)

        left_hip = (center_x - int(width * 0.16), hip_y)
        right_hip = (center_x + int(width * 0.16), hip_y)
        left_foot = (center_x - int(width * 0.3), bottom_y)
        right_foot = (center_x + int(width * 0.3), bottom_y)
        pygame.draw.line(screen, (152, 152, 152), left_hip, left_foot, 4)
        pygame.draw.line(screen, (152, 152, 152), right_hip, right_foot, 4)

        pygame.draw.line(
            screen,
            (60, 60, 60),
            (int(self.x), int(self.y + self.height)),
            (int(self.x + self.width), int(self.y + self.height)),
            2,
        )

        attack_rect = self.get_attack_rect()
        if attack_rect is not None:
            pygame.draw.rect(screen, (255, 220, 0), attack_rect, 2)
