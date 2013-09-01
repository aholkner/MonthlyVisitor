import bacon

GAME_WIDTH = 800
GAME_HEIGHT = 500

bacon.window.title = 'Monthly Visitor'
bacon.window.width = GAME_WIDTH
bacon.window.height = GAME_HEIGHT
#bacon.window.target = bacon.Image(width=GAME_WIDTH, height=GAME_HEIGHT, atlas=0)

image_cache = {}
def load_image(name):
    if isinstance(name, bacon.Image):
        return name

    try:
        return image_cache[name]
    except KeyError:
        image = image_cache[name] = bacon.Image('res/' + name, atlas=0) # atlas=0 workaround for #43
        return image

class SpriteSheet(object):
    def __init__(self, image, cols, rows):
        image = load_image(image)
        cell_width = int(image.width / cols)
        cell_height = int(image.height / rows)
        self.cells = []
        for row in range(rows):
            cell_row = []
            self.cells.append(cell_row)
            y = cell_height * row
            for col in range(cols):
                x = cell_width * col 
                cell = image.get_region(x, y, x + cell_width, y + cell_height)
                cell_row.append(cell)

def lpc_anims(image):
    sheet = SpriteSheet(image, 9, 4)
    up = sheet.cells[0]
    left = sheet.cells[1]
    down = sheet.cells[2]
    right = sheet.cells[3]
    def make_anim(images):
        anim = Anim([Frame(image, image.width / 2, image.height) for image in images])
        anim.time_per_frame = 0.1
        return anim

    return dict(
        idle_up = make_anim(up[:1]),
        walk_up = make_anim(up[1:]),
        idle_left = make_anim(left[:1]),
        walk_left = make_anim(left[1:]),
        idle_down = make_anim(down[:1]),
        walk_down = make_anim(down[1:]),
        idle_right = make_anim(right[:1]),
        walk_right = make_anim(right[1:])
    )

class Frame(object):
    def __init__(self, image, pivot_x, pivot_y):
        self.image = load_image(image)
        self.pivot_x = pivot_x
        self.pivot_y = pivot_y

class Anim(object):
    time_per_frame = 0.5

    def __init__(self, frames):
        self.frames = frames

class Sprite(object):
    def __init__(self, anim, x, y):
        self.anim = anim
        self.frame = anim.frames[0]
        self._time = 0
        self.x = x
        self.y = y

    def get_time(self):
        return self._time
    def set_time(self, time):
        self._time = time
        frame_index = int(time / self.anim.time_per_frame)
        self.frame = self.anim.frames[frame_index % len(self.anim.frames)]
    time = property(get_time, set_time)

    def draw(self):
        frame = self.frame
        x = self.x - frame.pivot_x
        y = self.y - frame.pivot_y
        bacon.draw_image(frame.image, x, y)

        # Update animation for next frame
        self.time += bacon.timestep

class Character(Sprite):
    walk_speed = 300
    facing = 'down'
    action = 'idle'

    def __init__(self, anims, x, y):
        self.anims = anims
        super(Character, self).__init__(self.get_anim(), x, y)

    def get_anim(self):
        try:
            return self.anims[self.action + '_' + self.facing]
        except KeyError:
            return self.anims[self.action]

    def update_player_movement(self):
        dx = 0
        dy = 0
        if bacon.Keys.up in bacon.keys:
            dy += -1
            self.facing = 'up'
        if bacon.Keys.down in bacon.keys:
            dy += 1
            self.facing = 'down'
        if bacon.Keys.left in bacon.keys:
            dx += -1
            self.facing = 'left'
        if bacon.Keys.right in bacon.keys:
            dx += 1
            self.facing = 'right'

        if dx or dy:
            speed = self.walk_speed / (dx * dx + dy * dy) * bacon.timestep
            self.x += dx * speed
            self.y += dy * speed
            self.action = 'walk'
        else:
            self.action = 'idle'

        self.anim = self.get_anim()

class Camera(object):
    def __init__(self):
        self.x = 0
        self.y = 0

    def apply(self):
        bacon.translate(-self.x + GAME_WIDTH / 2, -self.y + GAME_HEIGHT / 2)

camera = Camera()

player_anims = lpc_anims('BODY_male.png')
player = Character(player_anims, 0, 0)

rock_anim = Anim([Frame('rock.png', 16, 32)])
scenery = [
    Sprite(rock_anim, 100, 200)
]

class Game(bacon.Game):
    def on_tick(self):
        player.update_player_movement()
        camera.x = player.x
        camera.y = player.y

        bacon.clear(0.4, 0.3, 0.1, 1.0)
        camera.apply()

        for prop in scenery:
            prop.draw()
        player.draw()

bacon.run(Game())