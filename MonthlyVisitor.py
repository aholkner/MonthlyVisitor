from math import floor, sqrt
import os
import collections
import itertools
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

def spritesheet_anim(image, cols, rows, pivot_x, pivot_y):
    sheet = SpriteSheet(image, cols, rows)
    images = itertools.chain(*sheet.cells)
    return Anim([Frame(image, pivot_x, pivot_y) for image in images])

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
        self.target_item = None

    def get_anim(self):
        try:
            return self.anims[self.action + '_' + self.facing]
        except KeyError:
            return self.anims[self.action]

    def walk(self, arrived_func, hueristic_func):
        self.path = tilemap.get_path(tilemap.get_tile_at(self.x, self.y), arrived_func, hueristic_func)

    def walk_to_tile(self, tile):
        self.target_item = None
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
            self.target_item = None
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
                if self.target_item:
                    target_item = self.target_item
                    self.target_item = None
                    target_item.on_player_interact(target_tile)
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

def spawn_item_on_tile(tile, class_name, anim_name=None):
    try:
        cls = _spawn_classes[class_name]
    except KeyError:
        print('Missing spawn class %s' % class_name)
        return

    try:
        anim = object_anims[anim_name]
    except KeyError:
        anim = cls.get_default_anim()
        if not anim:
            return

    if tile:
        x = tile.rect.center_x
        y = tile.rect.center_y
        item = cls(anim, x, y)
        tile.items.append(item)
        tilemap.add_sprite(item)
    return item
    
class Item(Sprite):
    walkable = True
    can_pick_up = True
    anim_name = None
    name = None

    @classmethod
    def get_default_anim(cls):
        if not cls.anim_name:
            cls.anim_name = cls.__name__

        try:
            return object_anims[cls.anim_name]
        except KeyError:
            anim = object_anims[cls.anim_name] = Anim([Frame(cls.inventory_image, 16, 16)])
            return anim

    @classmethod
    def get_name(cls):
        if cls.name:
            return cls.name
        return cls.__name__

    def on_player_interact(self, tile):
        if self.can_pick_up:
            inventory.pick_up(self, tile)
        else:
            show_craft_menu(self)

    def on_pick_up(self):
        tilemap.remove_sprite(self)

    def on_dropped(self):
        tilemap.add_sprite(self)

@spawn
class Tree(Item):
    name = 'Tree'
    walkable = False
    can_pick_up = False
    anim_name = 'Tree1.png'

@spawn
class Wood(Item):
    name = 'Wood'
    anim_name ='Item-Wood.png'

@spawn
class Rock(Item):
    pass

@spawn
class Coal(Item):
    pass

@spawn
class Bone(Item):
    pass

@spawn
class RawMeat(Item):
    name = 'Raw Meat'

@spawn
class CookedMeat(Item):
    name = 'Cooked Meat'

@spawn
class Vegetable(Item):
    pass

@spawn
class Pick(Item):
    pass

@spawn
class Axe(Item):
    pass

@spawn
class Fire(Item):
    walkable = False
    can_pick_up = False

@spawn
class Fence(Item):
    walkable = False

@spawn
class StrongFence(Item):
    name = 'Strong Fence'
    walkable = False

@spawn
class Grass(Item):
    pass

@spawn
class Bread(Item):
    pass

@spawn
class Stick(Item):
    pass

@spawn
class Iron(Item):
    pass

@spawn
class Steel(Item):
    pass

@spawn
class Chicken(Item):
    pass

@spawn
class Rabbit(Item):
    pass



class Recipe(object):
    '''
    :param output: class to generate
    :param inputs: dict of class to count
    '''
    def __init__(self, output, inputs, text=None):
        if not isinstance(output, collections.Iterable):
            output = [output]
        self.outputs = output
        self.inputs = inputs
        self.text = text
        self.name = output[0].__name__
          
    def is_input(self, input):
        return input.__class__ in self.inputs

    def is_available(self):
        for input, count in self.inputs.items():
            if inventory.get_class_count(input) < count:
                return False
        return True

recipes = [
    Recipe(Axe, {Stick: 1, Rock: 1}),
    Recipe(Pick, {Stick: 1, Iron: 1}),
    #Recipe(Cage, {}),
    Recipe(Steel, {Fire: 1, Iron: 1, Coal: 1}),
    Recipe(Fire, {Wood: 2, Coal: 1}),
    Recipe(Fence, {Wood: 2}),
    Recipe(StrongFence, {Fence: 1, Wood: 2}),
    Recipe(RawMeat, {Chicken: 1}, 'Kill for meat'),
    Recipe([RawMeat, RawMeat], {Rabbit: 1}, 'Kill for meat'),
    Recipe(CookedMeat, {Fire: 1, RawMeat: 1}, 'Cook meat'),
    #Recipe(RabbitSnare)
    #Recipe(String
    #Recipe(Grass Suit
    #Recipe(FishingRod)

]

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


class MenuRecipeHint(object):
    def __init__(self, recipe):
        self.x = 0
        self.y = 0
        self.lines = []
        style = bacon.Style(font_ui)
        for (cls, count) in recipe.inputs.items():
            satisfied = inventory.get_class_count(cls) >= count
            text = '[%s] %dx %s' % ('X' if satisfied else ' ', count, cls.get_name())
            run = bacon.GlyphRun(style, text)
            self.lines.append(bacon.GlyphLayout([run], 0, 0, width=280, height=None, align=bacon.Alignment.left, vertical_align=bacon.VerticalAlignment.bottom))
        self.height = sum(line.content_height for line in self.lines)
        self.width = max(line.content_width for line in self.lines)

    def draw(self):
        x = self.x
        y = self.y
        bacon.set_color(0.2, 0.2, 0.2, 1.0)
        bacon.fill_rect(x, y, x + self.width, y - self.height)
        bacon.set_color(1, 1, 1, 1)
        for line in self.lines:
            line.x = x
            line.y = y
            bacon.draw_glyph_layout(line)
            y -= line.content_height

class MenuItem(object):
    def __init__(self, text, x, y, func, disabled=False, hint=None):
        self.text = text
        self.func = func
        self.disabled = disabled
        self.hint = hint
        style = bacon.Style(font_ui)
        width = 250
        self.glyph_layout = bacon.GlyphLayout([bacon.GlyphRun(style, text)], 
                                              x, y, 
                                              width, style.font.descent - style.font.ascent, 
                                              align=bacon.Alignment.left,
                                              vertical_align=bacon.VerticalAlignment.top)
        self.rect = Rect(x, y, x + self.glyph_layout.content_width, y + self.glyph_layout.content_height)

    def draw(self):
        if self.rect.contains(bacon.mouse.x, bacon.mouse.y):
            self.draw_hint()
            bacon.set_color(0.6, 0.6, 0.6, 1.0)
        else:
            bacon.set_color(0.3, 0.3, 0.3, 1.0)
        self.rect.fill()

        if self.disabled:
            bacon.set_color(0.7, 0.7, 0.7, 1.0)
        else:
            bacon.set_color(1.0, 1.0, 1.0, 1.0)
        bacon.draw_glyph_layout(self.glyph_layout)
        
    def draw_hint(self):
        if self.hint:
            self.hint.x = self.rect.x2
            self.hint.y = self.rect.y2
            self.hint.draw()

        

class Menu(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.item_y = y
        self.items = []
        self.rect = None

    def add(self, text, func=None, disabled=False, hint=None):
        item = MenuItem(text, 0, self.item_y, func, disabled=disabled, hint=hint)
        self.items.append(item)
        self.item_y = item.rect.y2
        self.rect = None

    def layout(self):
        width = max(item.rect.width for item in self.items)
        height = sum(item.rect.height for item in self.items)
        self.y -= height
        self.rect = Rect(self.x, self.y, self.x + width, self.y + height)
        for item in self.items:
            item.rect.y1 -= height
            item.rect.y2 -= height
            item.rect.x1 = self.x
            item.rect.x2 = item.rect.x1 + width
            item.glyph_layout.x = item.rect.x1
            item.glyph_layout.y = item.rect.y1
            
    def on_mouse_button(self, button, pressed):
        if not self.rect:
            self.layout()
        if self.rect.contains(bacon.mouse.x, bacon.mouse.y):
            for item in self.items:
                if item.rect.contains(bacon.mouse.x, bacon.mouse.y):
                    if item.func:
                        item.func()
                    game.menu = None
                    return
        if pressed:
            game.menu = None

    def draw(self):
        if not self.rect:
            self.layout()
        for item in self.items:
            item.draw()
            
class DropAction(object):
    def __init__(self, item):
        self.item = item

    def __call__(self):
        inventory.drop(self.item, player.get_drop_tile())

class CraftAction(object):
    def __init__(self, recipe, item):
        self.recipe = recipe
        self.item = item

    def __call__(self):
        inventory.craft(self.recipe, self.item)

def show_craft_menu(item):
    game.menu = Menu(item.x - 16, item.y - 32)

    for recipe in recipes:
        if recipe.is_input(item):
            text = recipe.text
            hint = MenuRecipeHint(recipe)
            if not text:
                text = 'Craft %s' % recipe.name
            if recipe.is_available():
                game.menu.add(text, CraftAction(recipe, item), hint=hint)
            else:
                game.menu.add(text, disabled=True, hint=hint)

    if item in inventory.items:
        tile = player.get_drop_tile()
        if tile:
            game.menu.add('Drop %s' % item.get_name(), DropAction(item))
        else:
            game.menu.add('Drop %s' % item.get_name(), disabled=True)

class Inventory(object):
    def __init__(self):
        self.items = []
        self.x = 32
        self.y = GAME_HEIGHT - 32
        self.item_size_x = 32
        self.item_size_y = 32

    def layout(self):
        for (i, item) in enumerate(self.items):
            item.x = self.x + i * self.item_size_x
            item.y = self.y

    def get_class_count(self, input_class):
        return len([i for i in self.items if i.__class__ is input_class])

    def get_item_at(self, x, y):
        for item in self.items:
            if item.rect.contains(x, y):
                return item

    def pick_up(self, item, tile):
        self.add_item(item)
        tile.remove_item(item)
        item.on_pick_up()
        
    def add_item(self, item):
        self.items.append(item)
        self.layout()

    def drop(self, item, tile):
        self.items.remove(item)
        tile.add_item(item)
        item.on_dropped()
        
    def craft(self, recipe, initial_item):
        slot_index = self.items.index(initial_item)
        for output in recipe.outputs:
            crafted_item = output(output.get_default_anim(), 0, 0)
            self.items.insert(slot_index, crafted_item)
        for item_class, count in recipe.inputs.items():
            for i in range(count):
                if initial_item and initial_item.__class__ is item_class:
                    self.items.remove(initial_item)
                    initial_item = None
                else:
                    for item in self.items:
                        if item.__class__ is item_class:
                            self.items.remove(item)
                            break
        self.layout()

    def draw(self):
        bacon.set_color(1, 1, 1, 1)
        for item in self.items:
            bacon.draw_image(item.inventory_image, item.x - 16, item.y - 16, item.x + 16, item.y + 16)

    def on_mouse_button(self, button, pressed):
        if pressed and button == bacon.MouseButtons.left:
            item = self.get_item_at(bacon.mouse.x, bacon.mouse.y)
            if item:
                show_craft_menu(item)
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
object_anims['Item-Fire'] = spritesheet_anim('Item-Fire.png', 1, 4, 16, 16)

tilemap = tiled.parse('res/Tilemap-Test.tmx')
for tileset in tilemap.tilesets:
    for image in tileset.images:
        if hasattr(image, 'properties'):
            props = image.properties
            if 'Class' in props:
                object_anims[props['Class'] + '-Inventory'] = Anim([Frame(image, 16, 16)])
                _spawn_classes[props['Class']].inventory_image = image

for layer in tilemap.layers:
    if layer.name == 'Spawns':
        tilemap.layers.remove(layer)
        for i, image in enumerate(layer.images):
            if image and hasattr(image, 'properties'):
                tile = tilemap.tiles[i]
                class_name = image.properties.get('Class')
                anim_name = image.properties.get('Anim')
                spawn_item_on_tile(tile, class_name, anim_name)

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
    def __init__(self):
        self.menu = None

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

        if self.menu:
            self.menu.draw()

    def on_key(self, key, pressed):
        if pressed and key == bacon.Keys.w:
            player.is_wolf = not player.is_wolf

    def on_mouse_button(self, button, pressed):
        if self.menu:
            self.menu.on_mouse_button(button, pressed)
            return

        if not player.is_wolf:
            if inventory.on_mouse_button(button, pressed):
                return

            if pressed and button == bacon.MouseButtons.left:
                x, y = camera.view_to_world(bacon.mouse.x, bacon.mouse.y)
                ti = tilemap.get_tile_index(x, y)
                tile = tilemap.tiles[ti]
                if tile.can_target and tile.walkable:
                    player.walk_to_tile(tile)
                    if tile.items:
                        player.target_item = tile.items[-1]

game = Game()
bacon.run(game)