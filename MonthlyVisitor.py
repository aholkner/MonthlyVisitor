from math import floor, sqrt
import os
# For profiling: import sys; sys.path.insert(0, '../bacon')

import bacon
import tiled
import spriter
from common import Rect

GAME_WIDTH = 800
GAME_HEIGHT = 500

bacon.window.title = 'Monthly Visitor'
bacon.window.width = GAME_WIDTH
bacon.window.height = GAME_HEIGHT
bacon.window.resizable = True

font_ui = bacon.Font(None, 16)

image_cache = {}
def load_image(name):
    if isinstance(name, bacon.Image):
        return name

    try:
        return image_cache[name]
    except KeyError:
        image = image_cache[name] = bacon.Image('res/' + name)
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

    def __lt__(self, other):
        return self.y < other.y

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
            inc = min(size, tilemap.tile_width / 2, tilemap.tile_height / 2)

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
        tilemap.update_sprite_position(self)

    def draw(self):
        frame = self.frame
        x = int(self.x - frame.pivot_x)
        y = int(self.y - frame.pivot_y)
        bacon.draw_image(frame.image, x, y)

        # Update animation for next frame
        self.time += bacon.timestep

class Character(Sprite):
    walk_speed = 200
    path_arrive_distance = 2
    facing = 'down'
    action = 'idle'

    is_wolf = False
    motive_food = 1.0
    motive_food_trigger = 0.5

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
        self.motive_food = max(self.motive_food - bacon.timestep * 0.01, 0)

    def update_wolf_motives(self):
        self.motive_food = max(self.motive_food - bacon.timestep * 0.05, 0)

        if self.motive_food < self.motive_food_trigger:
            if not self.path:
                # Search for nearby food -- note that the returned path is not optimal, but
                # looks more organic anyway
                self.walk(path_arrived_food(), path_hueristic_search())

    def get_drop_tile(self):
        return tilemap.get_tile_at(self.x, self.y)


_spawn_classes = {}
def spawn(cls):
    _spawn_classes[cls.__name__] = cls
    return cls

def spawn_item(tile, class_name, anim_name=None):
    try:
        cls = _spawn_classes[class_name]
    except KeyError:
        print('Missing spawn class %s' % class_name)
        return

    if anim_name is None:
        anim_name = cls.anim_name
    
    try:
        anim = object_anims[anim_name]
    except KeyError:
        print('Missing anim %s for class %s' % (anim_name, class_name))
        return

    item = cls(anim, tile.rect.center_x, tile.rect.center_y)
    tile.items.append(item)
    tilemap.add_sprite(item)

class Item(Sprite):
    walkable = True
    anim_name = None

    def on_pick_up(self, tile):
        tile.remove_item(self)
        tilemap.remove_sprite(self)

    def on_drop(self, tile):
        tile.add_item(self)
        tilemap.add_sprite(self)

@spawn
class Tree(Item):
    walkable = False
    anim_name = 'Tree1.png'

@spawn
class Wood(Item):
    anim_name ='Item-Wood.png'

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

    def get_bounds(self):
        return Rect(self.x - GAME_WIDTH / 2, self.y - GAME_HEIGHT / 2, self.x + GAME_WIDTH /2 , self.y + GAME_HEIGHT / 2)

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
        item.x = self.x + len(self.items) * self.item_size_x
        item.y = self.y
        item.on_pick_up(tile)
        
    def drop(self, item, tile):
        self.items.remove(item)
        item.on_drop(tile)
        
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



object_anims = {}
object_sprite_data = spriter.parse('res/Objects.scml')
for folder in object_sprite_data.folders:
    for file in folder.files:
        image = load_image(file.name)
        frame = Frame(image, file.pivot_x, file.pivot_y)
        anim = Anim([frame])
        object_anims[file.name] = anim

tilemap = tiled.parse('res/Tilemap-Test.tmx')
for layer in tilemap.layers:
    if layer.name == 'Spawns':
        tilemap.layers.remove(layer)
        for i, image in enumerate(layer.images):
            if image and hasattr(image, 'properties'):
                tile = tilemap.tiles[i]
                class_name = image.properties.get('Class')
                anim_name = image.properties.get('Anim')
                spawn_item(tile, class_name, anim_name)

camera = Camera()

player_anims = lpc_anims('BODY_male.png')
player = Character(player_anims, 0, 0)
tilemap.add_sprite(player)
inventory = Inventory()

for object_layer in tilemap.object_layers:
    for object in object_layer.objects:
        if object.name == 'PlayerStart':
            player.x = object.x
            player.y = object.y
            tilemap.update_sprite_position(player)

class Game(bacon.Game):
    def on_tick(self):
        if player.is_wolf:
            player.update_wolf_motives()
        else:
            player.update_player_motives()
            player.update_player_movement()
        
        player.update_walk_target_movement()

        camera.x = int(player.x)
        camera.y = int(player.y)

        bacon.clear(0.8, 0.7, 0.6, 1.0)
        bacon.push_transform()
        camera.apply()
        self.draw_world()
        bacon.pop_transform()

        self.draw_ui()
    
    def draw_world(self):
        bacon.set_color(1, 1, 1, 1)
        tilemap.draw(camera.get_bounds())

        if False:
            for tile in tilemap.tiles:
                if tile.path_current:
                    bacon.set_color(0, 0, 1, 1)
                    tile.rect.fill()
                elif tile.path_closed:
                    bacon.set_color(1, 1, 0, 1)
                    tile.rect.fill()
        
        bacon.set_color(0, 0, 1, 1)
        tilemap.get_tile_rect(player.x, player.y).draw()
        
        bacon.set_color(1, 0, 0, 1)
        
        tilemap.get_bounds().draw()
        
        
    def draw_ui(self):
        bacon.set_color(0, 0, 0, 1)
        if player.motive_food < player.motive_food_trigger:
            bacon.set_color(1, 0, 0, 1)
        bacon.draw_string(font_ui, 'Food level: %d%%' % round(player.motive_food * 100), GAME_WIDTH, 32, align=bacon.Alignment.right)
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
                if tile.can_target and (tile.items or tile.walkable):
                    player.walk_to_tile(tile)

bacon.run(Game())