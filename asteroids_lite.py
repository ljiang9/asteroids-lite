"""asteroids-lite：极简小行星游戏引擎。

物理：飞船推进/转向、子弹、小行星分裂（3→2→1）、环绕边界、碰撞。
支持 --auto 无头演示（AI 瞄准+推进）与文本渲染。
纯标准库：argparse / sys / random / math。
"""

import argparse
import math
import random
import sys

WIDTH, HEIGHT = 60, 24  # 文本格子
SHIP_R = 1.2            # 飞船碰撞半径（格）
BULLET_SPEED = 2.2     # 子弹相对速度（格/帧）
BULLET_LIFE = 60       # 子弹寿命（帧）
THRUST = 0.06          # 推进加速度
TURN = 0.12            # 每帧转向（弧度）
FRICTION = 0.995       # 惯性衰减
SAUCER_EVERY = 900     # UFO 每隔多少帧出现（演示用）
SPLIT_SCORE = {3: 20, 2: 50, 1: 100}


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def wrap(x, y):
    return (x % WIDTH, y % HEIGHT)


class Asteroid:
    def __init__(self, x, y, vx, vy, size):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.size = size  # 3 大 / 2 中 / 1 小

    @property
    def radius(self):
        return {3: 2.6, 2: 1.7, 1: 1.0}[self.size]

    def step(self):
        self.x, self.y = wrap(self.x + self.vx, self.y + self.vy)


class Bullet:
    def __init__(self, x, y, vx, vy):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = BULLET_LIFE

    def step(self):
        self.x, self.y = wrap(self.x + self.vx, self.y + self.vy)
        self.life -= 1


class Game:
    def __init__(self, seed=None, n_asteroids=5):
        self.rng = random.Random(seed)
        self.reset(n_asteroids)

    def reset(self, n_asteroids=5):
        self.ships_x, self.ships_y = WIDTH / 2, HEIGHT / 2
        self.vx, self.vy = 0.0, 0.0
        self.angle = -math.pi / 2  # 朝上
        self.asteroids = []
        self.bullets = []
        self.score = 0
        self.lives = 3
        self.frames = 0
        self.over = False
        self.won = False
        for _ in range(n_asteroids):
            self._spawn_asteroid(size=3, far_from_ship=True)

    def _spawn_asteroid(self, size, far_from_ship=False):
        for _ in range(100):
            x = self.rng.uniform(0, WIDTH)
            y = self.rng.uniform(0, HEIGHT)
            if far_from_ship and dist2((x, y), (self.ships_x, self.ships_y)) < 12 ** 2:
                continue
            break
        ang = self.rng.uniform(0, 2 * math.pi)
        spd = self.rng.uniform(0.15, 0.35)
        self.asteroids.append(Asteroid(x, y, math.cos(ang) * spd,
                                      math.sin(ang) * spd, size))

    # ---- 控制 ----
    def turn(self, direction):
        """direction: +1 左转 / -1 右转。"""
        self.angle += direction * TURN

    def thrust(self):
        self.vx += math.cos(self.angle) * THRUST
        self.vy += math.sin(self.angle) * THRUST

    def shoot(self):
        if len(self.bullets) >= 4:
            return
        bx = self.ships_x + math.cos(self.angle) * 1.5
        by = self.ships_y + math.sin(self.angle) * 1.5
        self.bullets.append(Bullet(
            bx, by,
            self.vx + math.cos(self.angle) * BULLET_SPEED,
            self.vy + math.sin(self.angle) * BULLET_SPEED))

    # ---- 推进一帧 ----
    def step(self):
        if self.over:
            return
        self.frames += 1
        # 飞船惯性
        self.vx *= FRICTION
        self.vy *= FRICTION
        self.ships_x, self.ships_y = wrap(self.ships_x + self.vx,
                                          self.ships_y + self.vy)
        for a in self.asteroids:
            a.step()
        for b in self.bullets:
            b.step()
        self.bullets = [b for b in self.bullets if b.life > 0]
        self._collide_bullets()
        self._collide_ship()
        if not self.asteroids and self.lives > 0:
            self.won = True
            self.over = True

    def _collide_bullets(self):
        """子弹命中：得分 + 分裂。"""
        dead_b, dead_a, new_a = set(), set(), []
        for bi, b in enumerate(self.bullets):
            for ai, a in enumerate(self.asteroids):
                if ai in dead_a:
                    continue  # 本帧已被击中，跳过（避免读到 size=0）
                if dist2((b.x, b.y), (a.x, a.y)) <= (a.radius + 0.4) ** 2:
                    dead_b.add(bi)
                    dead_a.add(ai)
                    self.score += SPLIT_SCORE[a.size]
                    if a.size > 1:
                        for _ in range(2):
                            ang = self.rng.uniform(0, 2 * math.pi)
                            spd = self.rng.uniform(0.2, 0.5)
                            new_a.append(Asteroid(
                                a.x, a.y,
                                a.vx + math.cos(ang) * spd,
                                a.vy + math.sin(ang) * spd,
                                a.size - 1))
                    break
        self.bullets = [b for i, b in enumerate(self.bullets) if i not in dead_b]
        self.asteroids = ([a for i, a in enumerate(self.asteroids)
                           if i not in dead_a] + new_a)

    def _collide_ship(self):
        for a in self.asteroids:
            if dist2((self.ships_x, self.ships_y), (a.x, a.y)) <= (a.radius + SHIP_R) ** 2:
                self.lives -= 1
                # 重生到中心并清速；撞到的那颗小行星分裂（惩罚感）
                self.ships_x, self.ships_y = WIDTH / 2, HEIGHT / 2
                self.vx = self.vy = 0.0
                if a.size > 1:
                    for _ in range(2):
                        ang = self.rng.uniform(0, 2 * math.pi)
                        self.asteroids.append(Asteroid(
                            a.x, a.y, math.cos(ang) * 0.3,
                            math.sin(ang) * 0.3, a.size - 1))
                    a.size = 0
                self.asteroids = [x for x in self.asteroids if x.size > 0]
                if self.lives <= 0:
                    self.over = True
                break

    # ---- 文本渲染 ----
    def render(self):
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for a in self.asteroids:
            ch = {3: "O", 2: "o", 1: "."}[a.size]
            grid[int(a.y) % HEIGHT][int(a.x) % WIDTH] = ch
        for b in self.bullets:
            grid[int(b.y) % HEIGHT][int(b.x) % WIDTH] = "-"
        sx, sy = int(self.ships_x) % WIDTH, int(self.ships_y) % HEIGHT
        grid[sy][sx] = "A"
        return "\n".join("".join(row) for row in grid)


def auto_play(seed=None, frames=600, verbose=False):
    """简单 AI：转向朝最近小行星开火，危险接近时推进逃离。"""
    g = Game(seed)
    for _ in range(frames):
        if g.over:
            break
        if g.asteroids:
            # 最近的小行星
            tgt = min(g.asteroids,
                      key=lambda a: dist2((g.ships_x, g.ships_y), (a.x, a.y)))
            dx = tgt.x - g.ships_x
            dy = tgt.y - g.ships_y
            # 环绕最短方向
            if dx > WIDTH / 2:
                dx -= WIDTH
            elif dx < -WIDTH / 2:
                dx += WIDTH
            if dy > HEIGHT / 2:
                dy -= HEIGHT
            elif dy < -HEIGHT / 2:
                dy += HEIGHT
            want = math.atan2(dy, dx)
            diff = (want - g.angle + math.pi) % (2 * math.pi) - math.pi
            if diff > 0.08:
                g.turn(1)
            elif diff < -0.08:
                g.turn(-1)
            else:
                g.shoot()
            # 危险：小行星太近则反向推进逃离
            nearest_d2 = min(dist2((g.ships_x, g.ships_y), (a.x, a.y))
                             for a in g.asteroids)
            if nearest_d2 < 6 ** 2:
                # 朝远离方向推进：直接反转朝向再推进
                away = math.atan2(-dy, -dx)
                diff2 = (away - g.angle + math.pi) % (2 * math.pi) - math.pi
                if abs(diff2) < 0.3:
                    g.thrust()
                elif diff2 > 0:
                    g.turn(1)
                else:
                    g.turn(-1)
        g.step()
        if verbose and g.frames % 100 == 0:
            print(f"帧 {g.frames}: 得分 {g.score}，小行星 {len(g.asteroids)}，生命 {g.lives}")
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(description="asteroids-lite：极简小行星游戏")
    ap.add_argument("--auto", action="store_true", help="无头自动演示")
    ap.add_argument("--frames", type=int, default=600, help="演示帧数")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--verbose", action="store_true", help="演示过程输出")
    args = ap.parse_args(argv)

    if args.auto:
        g = auto_play(seed=args.seed, frames=args.frames, verbose=args.verbose)
        print(f"自动演示结束：得分 {g.score}，剩余小行星 {len(g.asteroids)}，"
              f"生命 {g.lives}，帧数 {g.frames}，"
              f"{'胜利' if g.won else ('失败' if g.over else '未分胜负')}")
        return 0

    if not sys.stdin.isatty():
        print("交互模式需要终端；请用 --auto 看演示。", file=sys.stderr)
        return 2
    print("操作：a 左转 / d 右转 / w 推进 / s 开火 / q 退出（每行一个命令）")
    g = Game(args.seed)
    print(g.render())
    while not g.over:
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            break
        if cmd == "q":
            break
        elif cmd == "a":
            g.turn(1)
        elif cmd == "d":
            g.turn(-1)
        elif cmd == "w":
            g.thrust()
        elif cmd == "s":
            g.shoot()
        g.step()
        print(g.render())
        print(f"得分 {g.score} 生命 {g.lives}")
    print("游戏结束，得分", g.score)
    return 0


if __name__ == "__main__":
    sys.exit(main())
