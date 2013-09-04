from math import floor, sqrt
import os
import sys
import collections
import itertools
import random
# For profiling: import sys; sys.path.insert(0, '../bacon')

import bacon
import tiled
import spriter
from common import Rect

GAME_WIDTH = 800
GAME_HEIGHT = 500

# See Game.on_key for cheats
ENABLE_CHEATS = True
try:
    if sys.frozen:
        ENABLE_CHEATS = False
except AttributeError:
    pass

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
        
player_anims = lpc_anims('BODY_male.png')


def distance(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return sqrt(dx * dx + dy * dy)

class Waypoint(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

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

    def on_collide(self, tile):
        pass

    def on_moved_tile(self):
        pass

    def move_with_collision(self, tilemap, dx, dy, speed):
        # Slice movement into tile-sized blocks for collision testing
        size = sqrt(dx * dx + dy * dy)
        if not size:
            return False

        dx /= size
        dy /= size
        size = min(size, speed * bacon.timestep)
        did_move = False
        while size > 0:
            inc = min(size, tilemap.tile_width / 2, tilemap.tile_height / 2)

            # Move along X
            if dx:
                incx = inc * dx
                tile = tilemap.get_tile_at(self.x + incx, self.y)
                if tile.walkable:
                    self.x += incx
                    did_move = True
                else:
                    if dx > 0:
                        self.x = tile.rect.x1 - 1
                    elif dx < 0:
                        self.x = tile.rect.x2 + 1
                    if self.on_collide(tile):
                        return True

            # Move along Y
            if dy:
                incy = inc * dy
                tile = tilemap.get_tile_at(self.x, self.y + incy)
                if tile.walkable:
                    self.y += incy
                    did_move = True
                else:
                    if dy > 0:
                        self.y = tile.rect.y1 - 1
                    elif dy < 0:
                        self.y = tile.rect.y2 + 1
                    if self.on_collide(tile):
                        return True

            size -= inc
        
        tilemap.update_sprite_position(self)

        new_tile = tilemap.get_tile_at(self.x, self.y)
        if new_tile != self.current_tile:
            self.current_tile = new_tile
            self.on_moved_tile()

        return did_move

    def draw(self):
        frame = self.frame
        x = int(self.x - frame.pivot_x)
        y = int(self.y - frame.pivot_y)
        bacon.draw_image(frame.image, x, y)

        # Update animation for next frame
        self.time += bacon.timestep

class Character(Sprite):
    walk_speed = 200
    facing = 'down'
    action = 'idle'
    cooldown = 0

    is_wolf = False
    motive_food = 1.0
    motive_food_trigger = 0.5
    max_tilemap_path_size = 200

    distance_wolf_villager_search = GAME_WIDTH * 1.5
    distance_wolf_villager_attack = 16
    distance_wolf_waypoint_search = GAME_WIDTH * 1.5
    target_villager = None
    target_waypoint_index = -1
    eating_villager = False
    current_tile = None

    def __init__(self, anims, x, y):
        self.anims = anims
        super(Character, self).__init__(self.get_anim(), x, y)
        self.path = None
        self.target_item = None

    def wait(self, time):
        self.cooldown = max(self.cooldown, time)

    def get_anim(self):
        try:
            return self.anims[self.action + '_' + self.facing]
        except KeyError:
            return self.anims[self.action]

    def walk(self, arrived_func, hueristic_func):
        self.path = tilemap.get_path(tilemap.get_tile_at(self.x, self.y), arrived_func, hueristic_func, self.max_tilemap_path_size)
        return self.path != None

    def walk_to_tile(self, tile):
        self.target_item = None
        return self.walk(path_arrived(tile), path_heuristic_player(tile))

    def walk_to(self, x, y):
        tile = tilemap.get_tile_at(x, y)
        return self.walk_to_tile(tile)

    def walk_to_waypoint(self, target_index):
        self.target_waypoint_index = target_index
        waypoints.sort(key=lambda v:distance(v, self))
        for waypoint in waypoints:
            if distance(self, waypoint) < self.distance_wolf_waypoint_search:
                if self.walk_to(waypoint.x, waypoint.y):
                    return True
                

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
        if self.move_with_collision(tilemap, dx, dy, self.walk_speed):
            self.action = 'walk'
        else:
            # Didn't move, so we've arrived at this path node
            if self.path:
                del self.path[0]
                if not self.path:
                    self.on_arrive(target_tile)
                
        self.anim = self.get_anim()

    def on_collide(self, tile):
        if self.is_wolf:
            # Check for destructibles on tile
            for item in tile.items:
                if item.attackable_wolf:
                    item.on_attack()
                    return True

        if self.path:
            if self.path[0] == tile:
                # Arrived at non-walkable tile
                del self.path[0]
                if not self.path:
                    self.on_arrive(tile)
                    return

            # Path goes through a non-walkable tile, stop walking
            self.path = None
            self.target_item = None
            self.action = 'idle'

    def on_moved_tile(self):
        if self.eating_villager:
            # Random chance of blood dribble
            if random.random() < 0.3:
                spawn_blood(self.x, self.y, dribble=True)

    def on_arrive(self, tile):
        self.action = 'idle'
        if self.eating_villager:
            spawn_blood(self.x, self.y)
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneRibs')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneSkull')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneLegs')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'Bone')
            self.eating_villager = False
            self.add_food_motive(1.0)

        if self.target_item:
            target_item = self.target_item
            self.target_item = None
            target_item.on_player_interact(tile)

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
        
    def add_food_motive(self, amount):
        self.motive_food = min(self.motive_food + amount, 1.0)

    def update_player_motives(self):
        self.motive_food = max(self.motive_food - bacon.timestep * 0.01, 0)

    def update_wolf_motives(self):
        self.motive_food = max(self.motive_food - bacon.timestep * 0.05, 0)

        # If we've reached the villager we're after
        if self.target_villager and distance(self, self.target_villager) < self.distance_wolf_villager_attack:
            villagers.remove(self.target_villager)
            tilemap.remove_sprite(self.target_villager)
            self.target_villager = None
            self.eating_villager = True

            # Small bite
            self.add_food_motive(0.1)
            spawn_blood(self.x, self.y)
            self.walk_to_waypoint(1)
            return

        if self.cooldown > 0:
            self.cooldown -= bacon.timestep
            return

        # If we're standing on food, eat it
        tile = tilemap.get_tile_at(self.x, self.y)
        for item in tile.items:
            if item.food_wolf:
                ConsumeAction(item)()

        if self.motive_food < self.motive_food_trigger:
            if not self.path:
                # Search for nearby villagers
                villagers.sort(key=lambda v:distance(v, self))
                for villager in villagers:
                    if distance(self, villager) < self.distance_wolf_villager_search:
                        if self.walk_to(villager.x, villager.y): 
                            self.target_villager = villager
                            return

                # Search for nearby items that are food -- note that the returned path is not optimal, but
                # looks more organic anyway
                self.walk(path_arrived_wolf_food(), path_hueristic_wolf_search())

    def get_drop_tile(self):
        tile = tilemap.get_tile_at(self.x, self.y)
        if not tile.items:
            return tile

        if self.facing == 'left':
            tile = tilemap.get_tile_at(self.x - 32, self.y)
        elif self.facing == 'right':
            tile = tilemap.get_tile_at(self.x + 32, self.y)
        elif self.facing == 'up':
            tile = tilemap.get_tile_at(self.x, self.y - 32)
        elif self.facing == 'down':
            tile = tilemap.get_tile_at(self.x, self.y + 32)
        if not tile.items:
            return tile

        candidates = [
            tilemap.get_tile_at(self.x, self.y - 32),
            tilemap.get_tile_at(self.x, self.y + 32),
            tilemap.get_tile_at(self.x - 32, self.y),
            tilemap.get_tile_at(self.x + 32, self.y),
            tilemap.get_tile_at(self.x - 32, self.y - 32),
            tilemap.get_tile_at(self.x - 32, self.y + 32),
            tilemap.get_tile_at(self.x + 32, self.y - 32),
            tilemap.get_tile_at(self.x + 32, self.y + 32)
        ]
        random.shuffle(candidates)
        for candidate in candidates:
            if not candidate.items:
                return candidate

        return None

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
    is_consumed_in_recipe = True
    anim_name = None
    name = None
    food_human = 0
    food_wolf = 0
    path_cost_wolf = 0
    attackable_wolf = False

    @classmethod
    def get_default_anim(cls):
        anim_name = cls.anim_name
        if not cls.anim_name:
            anim_name = cls.__name__

        try:
            return object_anims[anim_name]
        except KeyError:
            anim = object_anims[anim_name] = Anim([Frame(cls.inventory_image, 16, 16)])
            return anim

    @classmethod
    def get_name(cls):
        if cls.name:
            return cls.name
        return cls.__name__

    def destroy(self):
        if self in inventory.items:
            inventory.remove(self)
        else:
            tile = tilemap.get_tile_at(self.x, self.y)
            tile.remove_item(self)
            tilemap.remove_sprite(self)

    def on_player_interact(self, tile):
        if self.can_pick_up:
            inventory.pick_up(self, tile)
        else:
            x, y = camera.world_to_view(self.x, self.y)
            show_craft_menu(self, x, y)

    def on_pick_up(self):
        tilemap.remove_sprite(self)

    def on_dropped(self):
        tilemap.add_sprite(self)

    def on_consumed_in_recipe(self):
        pass

    def on_consumed(self):
        if self.food_human and not player.is_wolf:
            player.add_food_motive(self.food_human)
        elif self.food_wolf and player.is_wolf:
            player.add_food_motive(self.food_wolf)
            player.wait(0.5)

    def on_attack(self):
        pass


@spawn
class Tree(Item):
    walkable = False
    can_pick_up = False
    anim_name = 'Tree1.png'
    path_cost_wolf = 99999

    def on_consumed_in_recipe(self):
        self.anim = object_anims['TreeStump']
        self.__class__ = TreeStump

@spawn
class TreeStump(Item):
    name = 'Tree Stump'
    can_pick_up = False
    
@spawn
class Wood(Item):
    name = 'Wood'

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
    food_wolf = 0.2

@spawn
class CookedMeat(Item):
    name = 'Cooked Meat'
    food_human = 0.3

@spawn
class Vegetable(Item):
    food_human = 0.05

@spawn
class Pick(Item):
    is_consumed_in_recipe = False

@spawn
class Axe(Item):
    is_consumed_in_recipe = False

@spawn
class Fire(Item):
    walkable = False
    path_cost_wolf = 99999
    can_pick_up = False

@spawn
class Fence(Item):
    walkable = False
    path_cost_wolf = 10
    attackable_wolf = True
    hp = 0.5
    fence_anims = {}

    def on_pick_up(self):
        super(Fence, self).on_pick_up()
        self.update_fence_and_adjacent()

    def on_dropped(self):
        super(Fence, self).on_dropped()
        self.update_fence_and_adjacent()

    def update_fence_and_adjacent(self):
        adjacent = [
            tilemap.get_tile_at(self.x - tilemap.tile_width, self.y),
            tilemap.get_tile_at(self.x + tilemap.tile_width, self.y),
            tilemap.get_tile_at(self.x, self.y - tilemap.tile_height),
            tilemap.get_tile_at(self.x, self.y + tilemap.tile_height),
        ]
        self.update_fence()
        for tile in adjacent:
            for item in tile.items:
                if isinstance(item, Fence):
                    item.update_fence()

    def update_fence(self):
        fmt = ''
        if self.has_neighbour_fence(self.x, self.y - tilemap.tile_height):
            fmt += 'U'
        if self.has_neighbour_fence(self.x, self.y + tilemap.tile_height):
            fmt += 'D'
        if self.has_neighbour_fence(self.x - tilemap.tile_width, self.y):
            fmt += 'L'
        if self.has_neighbour_fence(self.x + tilemap.tile_width, self.y):
            fmt += 'R'
        self.anim = self.fence_anims[fmt]

    def has_neighbour_fence(self, x, y):
        tile = tilemap.get_tile_at(x, y)
        for item in tile.items:
            if isinstance(item, Fence):
                return True
        return False

    def on_attack(self):
        self.hp -= bacon.timestep
        if self.hp <= 0:
            self.destroy()

@spawn
class StrongFence(Fence):
    name = 'Strong Fence'
    path_cost_wolf = 10
    hp = 2.0
    fence_anims = {}

@spawn
class Grass(Item):
    pass

@spawn
class Bread(Item):
    food_human = 0.2

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
    food_wolf = 0.3

    def on_consumed_in_recipe(self):
        spawn_blood(player.x, player.y)
        return super().on_consumed_in_recipe()

@spawn
class Rabbit(Item):
    food_wolf = 0.3

    def on_consumed_in_recipe(self):
        spawn_blood(player.x, player.y)
        return super().on_consumed_in_recipe()

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

    def is_available(self, extra_item):
        for input, count in self.inputs.items():
            if extra_item and extra_item.__class__ is input:
                count -= 1
            if inventory.get_class_count(input) < count:
                return False
        return True

recipes = [
    Recipe([Wood, Wood, Wood], {Axe: 1, Tree: 1}, 'Chop down for wood'),
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

def path_arrived_wolf_food():
    def func(tile):
        for item in tile.items:
            if item.food_wolf:
                return True
    return func

def path_hueristic_wolf_search():
    def func(tile):
        if not tile._walkable:
            return 99999
        if tile.items: 
            return max(item.path_cost_wolf for item in tile.items)
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

    def world_to_view(self, x, y):
        return x - self.x + GAME_WIDTH / 2, y - self.y + GAME_HEIGHT / 2

    def get_bounds(self):
        return Rect(self.x - GAME_WIDTH / 2, self.y - GAME_HEIGHT / 2, self.x + GAME_WIDTH /2 , self.y + GAME_HEIGHT / 2)

class MenuHint(object):
    def __init__(self):
        self.lines = []

    def layout(self):
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

class MenuRecipeHint(MenuHint):
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
        self.layout()


class MenuTextHint(MenuHint):
    def __init__(self, text):
        self.x = 0
        self.y = 0
        self.lines = []
        style = bacon.Style(font_ui)
        run = bacon.GlyphRun(style, text)
        self.lines.append(bacon.GlyphLayout([run], 0, 0, width=280, height=None, align=bacon.Alignment.left, vertical_align=bacon.VerticalAlignment.bottom))
        self.layout()

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
        tile = player.get_drop_tile()
        if tile:
            inventory.drop(self.item, tile)

class CraftAction(object):
    def __init__(self, recipe, item):
        self.recipe = recipe
        self.item = item

    def __call__(self):
        inventory.craft(self.recipe, self.item)

class ConsumeAction(object):
    def __init__(self, item):
        self.item = item

    def __call__(self):
        self.item.destroy()
        self.item.on_consumed()

def show_craft_menu(item, x, y):
    game.menu = Menu(x - 16, y - 32)

    extra_item = item if not item in inventory.items else None

    for recipe in recipes:
        if recipe.is_input(item):
            text = recipe.text
            hint = MenuRecipeHint(recipe)
            if not text:
                text = 'Craft %s' % recipe.name
            if recipe.is_available(extra_item):
                game.menu.add(text, CraftAction(recipe, item), hint=hint)
            else:
                game.menu.add(text, disabled=True, hint=hint)

    if item.food_human:
        game.menu.add('Eat %s' % item.get_name(), ConsumeAction(item))
    elif item.food_wolf:
        game.menu.add('Eat %s' % item.get_name(), disabled=True, hint=MenuTextHint('Can be eaten during full moon'))

    if item in inventory.items:
        tile = player.get_drop_tile()
        if tile:
            game.menu.add('Drop %s' % item.get_name(), DropAction(item))
        else:
            game.menu.add('Drop %s' % item.get_name(), disabled=True)

    if not game.menu.items:
        game.menu = None

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
        tile.remove_item(item)
        item.on_pick_up()
        self.add_item(item)
        
    def add_item(self, item):
        self.items.append(item)
        self.layout()

    def drop(self, item, tile):
        self.items.remove(item)
        tile.add_item(item)
        item.on_dropped()

    def remove(self, item):
        self.items.remove(item)
        self.layout()
        
    def craft(self, recipe, initial_item):
        if initial_item in self.items:
            slot_index = self.items.index(initial_item)
        else:
            slot_index = len(self.items)
        for output in recipe.outputs:
            crafted_item = output(output.get_default_anim(), 0, 0)
            self.items.insert(slot_index, crafted_item)
        for item_class, count in recipe.inputs.items():
            for i in range(count):
                if initial_item and initial_item.__class__ is item_class:
                    if initial_item.is_consumed_in_recipe:
                        if initial_item in self.items:
                            self.items.remove(initial_item)
                        initial_item.on_consumed_in_recipe()
                    initial_item = None
                else:
                    for item in self.items:
                        if item.__class__ is item_class:
                            if item.is_consumed_in_recipe:
                                self.items.remove(item)
                                item.on_consumed_in_recipe()
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
                show_craft_menu(item, item.x, item.y)
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

blood_images = []
blood_dribble_images = []
blood_layer = None

def spawn_blood(x, y, dribble=False):
    ti = tilemap.get_tile_index(x, y)
    if blood_layer.images[ti]:
        return

    if dribble:
        image = random.choice(blood_dribble_images)
    else:
        image = random.choice(blood_images)
    blood_layer.images[ti] = image

tilemap = tiled.parse('res/Tilemap-Test.tmx')
for tileset in tilemap.tilesets:
    for image in tileset.images:
        if hasattr(image, 'properties'):
            props = image.properties
            if 'Anim' in props:
                object_anims[props['Anim']] = Anim([Frame(image, 16, 16)])
            if 'Class' in props:
                _spawn_classes[props['Class']].inventory_image = image
            if 'Fence' in props:
                fmt = props['Fence']
                Fence.fence_anims[fmt] = Anim([Frame(image, 16, 16)])
            if 'StrongFence' in props:
                fmt = props['StrongFence']
                StrongFence.fence_anims[fmt] = Anim([Frame(image, 16, 16)])
            if 'Blood' in props:
                blood_images.append(image)
            if 'BloodDribble' in props:
                blood_dribble_images.append(image)

Fence.fence_anims[''] = Fence.get_default_anim()
StrongFence.fence_anims[''] = StrongFence.get_default_anim()

for layer in tilemap.layers:
    if layer.name == 'Spawns':
        tilemap.layers.remove(layer)
        for i, image in enumerate(layer.images):
            if image and hasattr(image, 'properties'):
                tile = tilemap.tiles[i]
                class_name = image.properties.get('Class')
                anim_name = image.properties.get('Anim')
                spawn_item_on_tile(tile, class_name, anim_name)
    elif layer.name == 'Blood':
        blood_layer = layer
camera = Camera()

player = Character(player_anims, 0, 0)
villagers = []
waypoints = []
tilemap.add_sprite(player)
inventory = Inventory()

for object_layer in tilemap.object_layers:
    for object in object_layer.objects:
        if object.name == 'PlayerStart':
            player.x = object.x
            player.y = object.y
            tilemap.update_sprite_position(player)
        elif object.name == 'Villager':
            villager = Character(player_anims, object.x, object.y)
            villagers.append(villager)
            tilemap.add_sprite(villager)
        elif object.name == 'Waypoint':
            waypoint = Waypoint(object.x, object.y)
            waypoints.append(waypoint)


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
        if ENABLE_CHEATS:
            if pressed and key == bacon.Keys.w:
                player.is_wolf = not player.is_wolf
            if pressed and key == bacon.Keys.minus:
                player.motive_food -= 0.2
            if pressed and key == bacon.Keys.plus:
                player.motive_food += 0.2

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
                if not player.walk_to_tile(tile):
                    # Path find failed, walk in straight line
                    player.path = [tile]
                if tile.items:
                    player.target_item = tile.items[-1]

game = Game()
bacon.run(game)