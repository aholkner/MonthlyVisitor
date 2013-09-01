import bacon

import heapq
from math import floor, sqrt

GAME_WIDTH = 800
GAME_HEIGHT = 500

bacon.window.title = 'Monthly Visitor'
bacon.window.width = GAME_WIDTH
bacon.window.height = GAME_HEIGHT

font_ui = bacon.Font(None, 16)

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

    @property
    def rect(self):
        x = self.x - self.frame.pivot_x
        y = self.y - self.frame.pivot_y
        return Rect(x, y, x + self.frame.image.width, y + self.frame.image.height)

    def move_with_collision(self, tilemap, dx, dy, speed):
        # Slice movement into tile-sized blocks for collision testing
        size = sqrt(dx * dx + dy * dy)
        dx /= size
        dy /= size
        size = min(size, speed * bacon.timestep)
        while size > 0:
            inc = min(size, tilemap.tile_size / 2)

            # Move along X
            incx = inc * dx
            tile = tilemap.get_tile_at(self.x + incx, self.y)
            if tile.walkable:
                self.x += incx
            elif dx > 0:
                self.x = tilemap.get_tile_rect(self.x + incx, self.y).x1 - 1
            elif dx < 0:
                self.x = tilemap.get_tile_rect(self.x + incx, self.y).x2 + 1

            # Move along Y
            incy = inc * dy
            tile = tilemap.get_tile_at(self.x, self.y + incy)
            if tile.walkable:
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
    path_arrive_distance = 2
    facing = 'down'
    action = 'idle'

    is_wolf = False

    def __init__(self, anims, x, y):
        self.anims = anims
        super(Character, self).__init__(self.get_anim(), x, y)
        self.path = None

    def get_anim(self):
        try:
            return self.anims[self.action + '_' + self.facing]
        except KeyError:
            return self.anims[self.action]

    def walk(self, arrived_func, hueristic_func):
        self.path = tilemap.get_path(tilemap.get_tile_at(self.x, self.y), arrived_func, hueristic_func)

    def walk_to_tile(self, tile):
        self.walk(path_arrived(tile), path_heuristic_player(tile))

    def update_player_movement(self):
        dx = 0
        dy = 0
        if bacon.Keys.up in bacon.keys:
            dy += -32
        if bacon.Keys.down in bacon.keys:
            dy += 32
        if bacon.Keys.left in bacon.keys:
            dx += -32 
        if bacon.Keys.right in bacon.keys:
            dx += 32

        if dx or dy:
            self.update_facing(dx, dy)
            self.move_with_collision(tilemap, dx, dy, self.walk_speed)
            self.path = None
            self.action = 'walk'
        elif not self.path:
            self.action = 'idle'

    def update_walk_target_movement(self):
        if not self.path:
            return

        target_tile = self.path[0]
        dx = target_tile.rect.center_x - self.x
        dy = target_tile.rect.center_y - self.y
        self.update_facing(dx, dy)
        distance = sqrt(dx * dx + dy * dy)
        if distance <= self.path_arrive_distance:
            del self.path[0]
            if not self.path:
                self.action = 'idle'
                if target_tile.items:
                    inventory.pick_up(target_tile)
        else:
            self.move_with_collision(tilemap, dx, dy, self.walk_speed)
            self.action = 'walk'

        self.anim = self.get_anim()

    def update_facing(self, dx, dy):
        if abs(dy) > abs(dx * 2):
            if dy < 0:
                self.facing = 'up'
            elif dy > 0:
                self.facing = 'down'
        elif dx < 0:
            self.facing = 'left'
        elif dx > 0:
            self.facing = 'right'
        
    def update_player_motives(self):
        pass

    def update_wolf_motives(self):
        if not self.path:
            # Search for nearby food -- note that the returned path is not optimal, but
            # looks more organic anyway
            self.walk(path_arrived_food(), path_hueristic_search())

    def get_drop_tile(self):
        return tilemap.get_tile_at(self.x, self.y)

class Item(Sprite):
    pass

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

    def contains(self, x, y):
        return (x >= self.x1 and
                x <= self.x2 and
                y >= self.y1 and
                y <= self.y2)

    def draw(self):
        bacon.draw_rect(self.x1, self.y1, self.x2, self.y2)

    def fill(self):
        bacon.fill_rect(self.x1, self.y1, self.x2, self.y2)

class Tile(object):
    path_cost = 1
    path_closed = False
    path_parent = None
    path_current = False

    def __init__(self, tx, ty, rect, walkable=True, accept_items=True):
        self.tx = tx
        self.ty = ty
        self.rect = rect
        self._walkable = walkable
        self.accept_items = accept_items
        self.can_target = True
        self.items = []

    def __lt__(self, other):
        return (self.tx, self.ty) < (other.tx, other.ty)

    def is_walkable(self):
        return self._walkable
    def set_walkable(self, walkable):
        self._walkable = walkable
    walkable = property(is_walkable, set_walkable)

    def add_item(self, item):
        self.items.append(item)
        item.x = self.rect.center_x
        item.y = self.rect.center_y

class Tilemap(object):
    tile_size = 32

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.tiles = []
        ts = self.tile_size
        y = 0
        for row in range(rows):
            x = 0
            for col in range(cols):
                self.tiles.append(Tile(col, row, Rect(x, y, x + ts, y + ts)))
                x += ts
            y += ts

        # default tile
        self.tiles.append(Tile(-1, -1, Rect(0, 0, 0, 0), walkable=False, accept_items=False))
        self.tiles[-1].can_target = False

    def get_tile_index(self, x, y):
        tx = floor(x / self.tile_size)
        ty = floor(y / self.tile_size)
        if (tx < 0 or tx >= self.cols or
            ty < 0 or ty >= self.rows):
            return len(self.tiles) - 1
        return int(ty * self.cols + tx)

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

    def get_path(self, start_tile, arrived_func, heuristic_func):
        # http://stackoverflow.com/questions/4159331/python-speed-up-an-a-star-pathfinding-algorithm
        for tile in self.tiles:
            tile.path_parent = None
            tile.path_closed = False
            tile.path_open = False
            tile.path_current = False
        
        def retrace(c):
            path = [c]
            while c.path_parent is not None:
                c.path_current = True
                c = c.path_parent
                path.append(c)
            path.reverse()
            return path
        
        def candidates(tile):
            tx = tile.tx
            ty = tile.ty
            i = ty * self.cols + tx
            left = right = up = down = None
            if tx > 0:
                left = self.tiles[i - 1]
                yield left
            if tx < self.cols - 1:
                right = self.tiles[i + 1]
                yield right
            if ty > 0:
                up = self.tiles[i - self.cols]
                yield up
            if ty < self.rows - 1:
                down = self.tiles[i + self.cols]
                yield down
            if left and left.walkable:
                if up and up.walkable:
                    yield self.tiles[i - self.cols - 1]
                if down and down.walkable:
                    yield self.tiles[i + self.cols - 1]
            if right and right.walkable:
                if up and up.walkable:
                    yield self.tiles[i - self.cols + 1]
                if down and down.walkable:
                    yield self.tiles[i + self.cols + 1]

        open = []
        open.append((0, start_tile))
        while open:
            score, current = heapq.heappop(open)
            if arrived_func(current):
                return retrace(current)
            current.path_closed = True
            for tile in candidates(current):
                if not tile.path_closed and not tile.path_open:
                    g = heuristic_func(tile)
                    tile.path_open = True
                    heapq.heappush(open, (score + g + 1, tile))
                    tile.path_parent = current
        return []

def path_arrived(destination):
    def func(tile):
        return tile is destination
    return func

def path_heuristic_player(destination):
    def func(tile):
        if not tile.walkable:
            return 99999
        return abs(destination.tx - tile.tx) + abs(destination.ty - tile.ty) + tile.path_cost
    return func

def path_arrived_food():
    def func(tile):
        return tile.items
    return func

def path_hueristic_search():
    def func(tile):
        if not tile.walkable:
            return 99999
        return tile.path_cost
    return func

class Camera(object):
    def __init__(self):
        self.x = 0
        self.y = 0

    def apply(self):
        bacon.translate(-self.x + GAME_WIDTH / 2, -self.y + GAME_HEIGHT / 2)

    def view_to_world(self, x, y):
        return x + self.x - GAME_WIDTH / 2, y + self.y - GAME_HEIGHT / 2

class Inventory(object):
    def __init__(self):
        self.items = []
        self.x = 0
        self.y = GAME_HEIGHT - 32
        self.item_size_x = 32
        self.item_size_y = 32

    def get_item_at(self, x, y):
        for item in self.items:
            if item.rect.contains(x, y):
                return item

    def pick_up(self, tile):
        item = tile.items[-1]
        self.items.append(item)
        del tile.items[-1]
        item.x = self.x + len(self.items) * self.item_size_x
        item.y = self.y

    def drop(self, item, tile):
        tile.add_item(item)
        self.items.remove(item)
        
    def draw(self):
        bacon.set_color(1, 1, 1, 1)
        x = 0
        for item in self.items:
            item.draw()
            x += 32

    def on_mouse_button(self, button, pressed):
        if pressed and button == bacon.MouseButtons.left:
            item = self.get_item_at(bacon.mouse.x, bacon.mouse.y)
            if item:
                tile = player.get_drop_tile()
                if tile and tile.accept_items:
                    self.drop(item, tile)
                return True
        return False

tilemap = Tilemap(10, 10)

camera = Camera()

player_anims = lpc_anims('BODY_male.png')
player = Character(player_anims, 0, 0)
inventory = Inventory()

rock_anim = Anim([Frame('rock.png', 16, 16)])
meat_anim = Anim([Frame('meat.png', 16, 16)])
scenery = [
    Sprite(rock_anim, 32*2, 32*8),
    Sprite(rock_anim, 32*2, 32*7),
    Sprite(rock_anim, 32*2, 32*6),
]
for sprite in scenery:
    tilemap.get_tile_at(sprite.x, sprite.y).walkable = False
    tilemap.get_tile_at(sprite.x, sprite.y).accept_items = False

tilemap.get_tile_at(32+16, 32+16).items.append(Item(meat_anim, 32+16, 32+16))
tilemap.get_tile_at(32*8+16, 32*4+16).items.append(Item(meat_anim, 32*8+16, 32*4+16))

class Game(bacon.Game):
    def on_tick(self):
        if player.is_wolf:
            player.update_wolf_motives()
        else:
            player.update_player_motives()
            player.update_player_movement()
        
        player.update_walk_target_movement()

        camera.x = player.x
        camera.y = player.y

        bacon.clear(0.8, 0.7, 0.6, 1.0)
        bacon.push_transform()
        camera.apply()
        self.draw_world()
        bacon.pop_transform()

        self.draw_ui()
    
    def draw_world(self):
        for tile in tilemap.tiles:
            if tile.path_current:
                bacon.set_color(0, 0, 1, 1)
                tile.rect.fill()
            elif tile.path_closed:
                bacon.set_color(1, 1, 0, 1)
                tile.rect.fill()
        bacon.set_color(1, 1, 1, 1)

        for prop in scenery:
            prop.draw()
            tilemap.get_tile_rect(prop.x, prop.y).draw()
        for tile in tilemap.tiles:
            for item in tile.items:
                item.draw()
        player.draw()

        bacon.set_color(0, 0, 1, 1)
        tilemap.get_tile_rect(player.x, player.y).draw()
        bacon.set_color(1, 0, 0, 1)
        tilemap.get_bounds().draw()
        
    def draw_ui(self):
        inventory.draw()

        if player.is_wolf:
            bacon.set_color(0, 0, 0, 1)
            bacon.draw_string(font_ui, 'WOLF', 0, 32)

    def on_key(self, key, pressed):
        if pressed and key == bacon.Keys.w:
            player.is_wolf = not player.is_wolf

    def on_mouse_button(self, button, pressed):
        if not player.is_wolf:
            if inventory.on_mouse_button(button, pressed):
                return

            if pressed and button == bacon.MouseButtons.left:
                x, y = camera.view_to_world(bacon.mouse.x, bacon.mouse.y)
                ti = tilemap.get_tile_index(x, y)
                tile = tilemap.tiles[ti]
                if tile.can_target:
                    player.walk_to_tile(tile)

bacon.run(Game())