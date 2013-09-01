import bacon

from math import floor, sqrt

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
        anim = Anim([Frame(image, image.width / 2, image.height - 10) for image in images])
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

    def move_with_collision(self, tilemap, dx, dy):
        # Slice movement into tile-sized blocks for collision testing
        size = sqrt(dx * dx + dy * dy)
        dx /= size
        dy /= size
        while size > 0:
            inc = min(size, tilemap.tile_size / 2)

            # Move along X
            incx = inc * dx
            ti = tilemap.get_tile_index(self.x + incx, self.y)
            if tilemap.tiles[ti].walkable:
                self.x += incx
            elif dx > 0:
                self.x = tilemap.get_tile_rect(self.x + incx, self.y).x1 - 1
            elif dx < 0:
                self.x = tilemap.get_tile_rect(self.x + incx, self.y).x2 + 1

            # Move along Y
            incy = inc * dy
            ti = tilemap.get_tile_index(self.x, self.y + incy)
            if tilemap.tiles[ti].walkable:
                self.y += incy
            elif dy > 0:
                self.y = tilemap.get_tile_rect(self.x, self.y + incy).y1 - 1
            elif dy < 0:
                self.y = tilemap.get_tile_rect(self.x, self.y + incy).y2 + 1

            size -= inc

    def draw(self):
        frame = self.frame
        x = self.x - frame.pivot_x
        y = self.y - frame.pivot_y
        bacon.draw_image(frame.image, x, y)

        # Update animation for next frame
        self.time += bacon.timestep

class Character(Sprite):
    walk_speed = 200
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

    def update_player_movement(self, tilemap):
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
            speed = self.walk_speed / sqrt(dx * dx + dy * dy) * bacon.timestep
            self.move_with_collision(tilemap, dx * speed, dy * speed)
            self.action = 'walk'
        else:
            self.action = 'idle'

        self.anim = self.get_anim()

class Rect(object):
    def __init__(self, x1, y1, x2, y2):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    @property
    def center_x(self):
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self):
        return (self.y1 + self.y2) / 2

    def draw(self):
        bacon.draw_rect(self.x1, self.y1, self.x2, self.y2)

    def fill(self):
        bacon.fill_rect(self.x1, self.y1, self.x2, self.y2)

class Tile(object):
    def __init__(self, walkable=True):
        self.walkable = walkable

class Tilemap(object):
    tile_size = 32

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.tiles = [Tile() for i in range(cols * rows + 1)]

        # default tile
        self.tiles[-1] = Tile(walkable=False)

    def get_tile_index(self, x, y):
        tx = floor(x / self.tile_size)
        ty = floor(y / self.tile_size)
        if (tx < 0 or tx >= self.cols or
            ty < 0 or ty >= self.rows):
            return len(self.tiles) - 1
        return ty * self.cols + tx

    def get_tile_at(self, x, y):
        return self.tiles[self.get_tile_index(x, y)]

    def get_tile_rect(self, x, y):
        tx = floor(x / self.tile_size)
        ty = floor(y / self.tile_size)
        x = tx * self.tile_size
        y = ty * self.tile_size
        return Rect(x, y, x + self.tile_size, y + self.tile_size)

    def get_bounds(self):
        return Rect(0, 0, self.cols * self.tile_size, self.rows * self.tile_size)

class Camera(object):
    def __init__(self):
        self.x = 0
        self.y = 0

    def apply(self):
        bacon.translate(-self.x + GAME_WIDTH / 2, -self.y + GAME_HEIGHT / 2)

tilemap = Tilemap(10, 10)

camera = Camera()

player_anims = lpc_anims('BODY_male.png')
player = Character(player_anims, 0, 0)

rock_anim = Anim([Frame('rock.png', 16, 32)])
scenery = [
    Sprite(rock_anim, 100, 200)
]
tilemap.get_tile_at(scenery[0].x, scenery[0].y).walkable = False

class Game(bacon.Game):
    def on_tick(self):
        player.update_player_movement(tilemap)
        camera.x = player.x
        camera.y = player.y

        bacon.clear(0.4, 0.3, 0.1, 1.0)
        camera.apply()
        
        for prop in scenery:
            prop.draw()
            tilemap.get_tile_rect(prop.x, prop.y).draw()
        player.draw()

        bacon.set_color(0, 0, 1, 1)
        tilemap.get_tile_rect(player.x, player.y).draw()
        bacon.set_color(1, 0, 0, 1)
        tilemap.get_bounds().draw()

bacon.run(Game())