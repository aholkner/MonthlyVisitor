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
import moon
from common import Rect, tween, update_tweens

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
bacon.window.resizable = False
bacon.window.content_scale = 1.0

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

def lpc_anims(image, cols, rows):
    sheet = SpriteSheet(image, cols, rows)
    up = sheet.cells[0]
    left = sheet.cells[1]
    down = sheet.cells[2]
    right = sheet.cells[3]
    def make_anim(images):
        anim = Anim([Frame(image, image.width / 2, image.height - 10) for image in images])
        anim.time_per_frame = 0.1
        return anim

    if cols > 4:
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
    else:
        return dict(
            idle_up = make_anim(up[:1]),
            walk_up = make_anim(up),
            idle_left = make_anim(left[:1]),
            walk_left = make_anim(left),
            idle_down = make_anim(down[:1]),
            walk_down = make_anim(down),
            idle_right = make_anim(right[:1]),
            walk_right = make_anim(right)
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
        
player_anims = lpc_anims('BODY_male.png', 9, 4)
player_anims['death'] = spritesheet_anim('Player-Extra.png', 6, 1, 32, 54)

chicken_anims = lpc_anims('Chicken.png', 4, 4)


def distance(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return sqrt(dx * dx + dy * dy)

def dot(ax, ay, bx, by):
    return ax * bx + ay * by

class Waypoint(object):
    index = 0
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Sprite(object):
    looping = True

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
        old_time = self._time
        self._time = time
        frame_index = int(time / self.anim.time_per_frame)
        if self.looping:
            self.frame = self.anim.frames[frame_index % len(self.anim.frames)]
        else:
            self.frame = self.anim.frames[min(frame_index, len(self.anim.frames) - 1)]
            old_frame_index = int(old_time / self.anim.time_per_frame)
            if old_frame_index < len(self.anim.frames) and frame_index >= len(self.anim.frames):
                self.on_anim_finished()
    time = property(get_time, set_time)

    @property
    def rect(self):
        x = self.x - self.frame.pivot_x
        y = self.y - self.frame.pivot_y
        return Rect(x, y, x + self.frame.image.width, y + self.frame.image.height)

    def on_anim_finished(self):
        pass

    def on_collide(self, tile):
        pass

    def on_moved_tile(self):
        pass

    def can_walk(self, tile):
        return tile.walkable

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
                if self.can_walk(tile):
                    self.x += incx
                    did_move = True
                else:
                    if dx > 0:
                        self.x = tile.rect.x1 - 1
                    elif dx < 0:
                        self.x = tile.rect.x2 + 1
                    return self.on_collide(tile)

            # Move along Y
            if dy:
                incy = inc * dy
                tile = tilemap.get_tile_at(self.x, self.y + incy)
                if self.can_walk(tile):
                    self.y += incy
                    did_move = True
                else:
                    if dy > 0:
                        self.y = tile.rect.y1 - 1
                    elif dy < 0:
                        self.y = tile.rect.y2 + 1
                    return self.on_collide(tile)

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
    name = None
    
    running = False
    walk_speed = 200
    run_speed = 220
    facing = 'down'
    action = 'idle'
    cooldown = 0
    
    is_wolf = False
    is_dying = False
    motive_food = 1.0
    motive_food_trigger = 0.8
    max_tilemap_path_size = 500
    distance_player_pickup_animal = 24

    distance_wolf_villager_search = GAME_WIDTH * 1.5
    distance_wolf_villager_attack = 32
    target_villager = None
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

    def die(self):
        if self.is_dying:
            return

        self.is_dying = True
        self.action = 'death'
        self.path = None
        self.looping = False
        self.time = 0
        self.anim = self.get_anim()

    def on_anim_finished(self):
        if self.is_dying:
            game.screen = GameOverScreen()

    def walk(self, arrived_func, hueristic_func):
        self.path = tilemap.get_path(tilemap.get_tile_at(self.x, self.y), arrived_func, hueristic_func, self.max_tilemap_path_size)
        return self.path

    def walk_to_tile(self, tile):
        self.target_item = None
        return self.walk(path_arrived(tile), path_heuristic_player(tile))

    def walk_to(self, x, y):
        tile = tilemap.get_tile_at(x, y)
        return self.walk_to_tile(tile)    

    def walk_to_distant_object(self, obj):
        if distance(obj, self) > GAME_WIDTH * 0.5:
            dx = obj.x - self.x
            dy = obj.y - self.y
            m = GAME_WIDTH * 0.25 / sqrt(dx * dx + dy * dy)
            dx *= m
            dy *= m
            return self.walk_to(self.x + dx, self.y + dy)
        else:
            return self.walk_to(obj.x, obj.y)

    def walk_to_waypoint(self, target_index=None):
        waypoints.sort(key=lambda v:distance(v, self))
        for waypoint in waypoints:
            if target_index is not None and waypoint.index != target_index:
                continue
            
            if self.walk_to_distant_object(waypoint):
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
            self.move_with_collision(tilemap, dx, dy, self.run_speed if self.running else self.walk_speed)
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
        if self.move_with_collision(tilemap, dx, dy, self.run_speed if self.running else self.walk_speed):
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
                    return False

            # Path goes through a non-walkable tile, stop walking
            self.path = None
            self.target_item = None
            self.action = 'idle'
            return False

    def on_moved_tile(self):
        if self.eating_villager:
            # Random chance of blood dribble
            if random.random() < 0.3:
                spawn_blood(self.x, self.y, dribble=True)

    def on_arrive(self, tile):
        self.action = 'idle'

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
        self.motive_food = max(self.motive_food - bacon.timestep * 0.05, 0.01)

        # If we've reached the villager we're after
        if self.target_villager and distance(self, self.target_villager) < self.distance_wolf_villager_attack:
            # Remove villager's factories
            if self.target_villager.name:
                factories[:] = [f for f in factories if f.owner != self.target_villager.name]

            # Remove villager
            villagers.remove(self.target_villager)
            tilemap.remove_sprite(self.target_villager)
            self.target_villager = None
            self.eating_villager = True

            # Small bite
            self.add_food_motive(0.1)
            spawn_blood(self.x, self.y)
            self.walk_to_waypoint()
            self.wait(0.8)
            return

        if self.cooldown > 0:
            self.cooldown -= bacon.timestep
            self.action = 'idle'
            self.anim = self.get_anim()
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
                if self.walk(path_arrived_wolf_food(), path_hueristic_wolf_search()):
                    return

                # Walk towards nearest villager over multiple screens
                for villager in villagers:
                    if self.walk_to_distant_object(villagers[0]):
                        self.target_villager = villager
                        return

        if not self.path:
            # Random walk
            dx = random.randrange(-3, 3) * 32
            dy = random.randrange(-3, 3) * 32
            self.wait(random.randrange(1, 2))
            self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]

        self.update_walk_target_movement()

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

    
class Player(Character):
    def start_wolf(self):
        self.is_wolf = True
        self.path = None
        self.running = True
        self.action = 'idle'
        self.anim = self.get_anim()
        for item in inventory.items[:]:
            inventory.drop(item, self.get_drop_tile())

    def end_wolf(self):
        self.is_wolf = False
        self.path = None
        self.running = False
        self.action = 'idle'
        self.anim = self.get_anim()
        if self.eating_villager:
            self.on_arrive(tilemap.get_tile_at(self.x, self.y))
    
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
            self.wait(2.5)

        # Check if we arrived on an animal
        for animal in animals:
            if distance(self, animal) < self.distance_player_pickup_animal:
                if animal.snared:
                    # Remove the snare
                    for item in tile.items:
                        if item is self.target_item:
                            self.target_item = None
                        if isinstance(item, Snare):
                            item.destroy()

                if not self.target_item:
                    # Only pick up the animal if it was snared and we were targetting the snare,
                    # or we weren't targetting anything.
                    item = animal.item_cls(animal.item_cls.get_default_anim(), 0, 0)
                    inventory.add_item(item)
                    tilemap.remove_sprite(animal)
                    animals.remove(animal)
                    return

        # Normal pick_up
        if self.target_item:
            target_item = self.target_item
            self.target_item = None
            target_item.on_player_interact(tile)


class Animal(Character):
    walk_speed = 50
    run_speed = 110

    run_cooldown = 0
    run_cooldown_time = 1.5 # How long to run before exhaustion
    danger_radius = 100

    snare_attract_radius = 128
    snare_catch_radius = 8
    snared = False

    def can_walk(self, tile):
        return tile.walkable and tile.walkable_animal

    def update_animal_movement(self):
        if self.running:
            self.run_cooldown -= bacon.timestep

        if not self.path:
            if distance(self, player) < self.danger_radius and self.run_cooldown > 0:
                self.running = True
                self.run_cooldown -= bacon.timestep
                dx = random.randrange(1, 5) * 32
                dy = random.randrange(0, 5) * 32
                if player.x > self.x:
                    dx = -dx
                if player.y > self.y:
                    dy = -dy
                self.wait(random.randrange(1, 4) / 4.0)
            else:
                if self.running:
                    self.running = False
                    self.wait(2)
                    return

                if self.cooldown > 0:
                    self.cooldown -= bacon.timestep
                    return

                # Reset exhaustion
                self.run_cooldown = self.run_cooldown_time
                
                # Check for nearby snares
                for snare in snares:
                    if distance(snare, self) < self.snare_catch_radius:
                        self.snared = True
                    elif distance(snare, self) < self.snare_attract_radius:
                        self.running = False
                        self.path = [tilemap.get_tile_at(snare.x, snare.y)]
                
                # Random walk
                if not self.path and not self.snared:
                    dx = random.randrange(-4, 4) * 32
                    dy = random.randrange(-4, 4) * 32
                    self.wait(random.randrange(1, 8))
                    self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]
            
        if self.snared:
            self.anim = self.get_anim()
        else:
            self.update_walk_target_movement()


    def on_collide(self, tile):
        if self.running:
            self.cooldown = 0


class Villager(Character):
    walk_speed = 50
    run_speed = 50

    def can_walk(self, tile):
        if not tile.walkable_villager:
            return False
        return tile.walkable and tile.walkable_villager

    def update_villager_movement(self):
        if not self.path:
            if self.cooldown > 0:
                self.cooldown -= bacon.timestep
                return
            dx = random.randrange(-4, 4) * 32
            dy = random.randrange(-4, 4) * 32
            self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]
            self.wait(random.randrange(1, 8))
        self.update_walk_target_movement()


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

    def on_dropped(self, tile):
        tile.add_item(self)
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
class BerryPlant(Item):
    name = 'Berry Plant'
    can_pick_up = False

    def on_consumed_in_recipe(self):
        self.anim = object_anims['BerryPlantEmpty']
        self.__class__ = BerryPlantEmpty

@spawn
class BerryPlantEmpty(Item):
    name = 'Berry Plant'
    can_pick_up = False

@spawn
class Berries(Item):
    food_human = 0.05

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

    def on_dropped(self, tile):
        super(Fence, self).on_dropped(tile)
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
class Grass(Item):
    pass

@spawn
class Rope(Item):
    pass

@spawn
class Snare(Item):
    def on_dropped(self, tile):
        super(Snare, self).on_dropped(tile)
        snares.append(self)

    def on_pick_up(self):
        try:
            snares.remove(self)
        except ValueError:
            pass

@spawn
class Chicken(Item):
    food_wolf = 0.3

    def on_dropped(self, tile):
        animal = Animal(chicken_anims, tile.rect.center_x, tile.rect.center_y)
        animal.item_cls = self.__class__
        tilemap.add_sprite(animal)
        animals.append(animal)

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
    Recipe(Snare, {Rope: 2, Vegetable: 1}),
    Recipe(Rope, {Grass: 3}),
    Recipe(Berries, {BerryPlant: 1}, 'Pick berries'),
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

class Factory(object):
    def __init__(self, tile, spawn_class_name, owner=None, cooldown_time=5):
        self.spawn_class_name = spawn_class_name
        self.tile = tile
        self.cooldown_time = cooldown_time
        self.cooldown = 0
        self.owner = owner

    def produce(self):
        if not self.tile.items:
            spawn_item_on_tile(self.tile, self.spawn_class_name)

    def update(self):
        if self.tile.items:
            self.cooldown = self.cooldown_time
        else:
            self.cooldown -= bacon.timestep
            if self.cooldown <= 0:
                self.produce()

factories = []

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

    def clamp_to_bounds(self, bounds):
        if self.x - GAME_WIDTH / 2 < bounds.x1:
            self.x = bounds.x1 + GAME_WIDTH / 2
        if self.x + GAME_WIDTH / 2 > bounds.x2:
            self.x = bounds.x2 - GAME_WIDTH / 2
        if self.y - GAME_HEIGHT / 2 < bounds.y1:
            self.y = bounds.y1 + GAME_HEIGHT / 2
        if self.y + GAME_HEIGHT / 2 > bounds.y2:
            self.y = bounds.y2 - GAME_HEIGHT / 2

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
        if tile:
            item.on_dropped(tile)

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

tilemap = tiled.parse('res/Tilemap.tmx')
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

class Tutorial(object):
    def __init__(self, text, rect):
        self.text = text
        self.rect = rect

player = Player(player_anims, 0, 0)
villagers = []
animals = []
waypoints = []
snares = []
tilemap.add_sprite(player)
inventory = Inventory()
tutorials = []


for layer in tilemap.layers:
    if layer.name == 'Spawns':
        tilemap.layers.remove(layer)
        for i, image in enumerate(layer.images):
            if image and hasattr(image, 'properties'):
                tile = tilemap.tiles[i]
                class_name = image.properties.get('Class')
                anim_name = image.properties.get('Anim')
                if class_name == 'Chicken':
                    animal = Animal(chicken_anims, tile.rect.center_x, tile.rect.center_y)
                    animal.item_cls = Chicken
                    animals.append(animal)
                    tilemap.add_sprite(animal)
                elif class_name:
                    spawn_item_on_tile(tile, class_name, anim_name)
                
                factory_class = image.properties.get('FactoryClass')
                if factory_class:
                    owner = image.properties.get('Owner')
                    cooldown = int(image.properties.get('Cooldown', 5))
                    factories.append(Factory(tile, factory_class, owner, cooldown))

                if image.properties.get('Waypoint'):
                    waypoint = Waypoint(tile.rect.center_x, tile.rect.center_y)
                    waypoints.append(waypoint)
    elif layer.name == 'Blood':
        blood_layer = layer
camera = Camera()


for object_layer in tilemap.object_layers:
    for obj in object_layer.objects:
        if obj.name == 'PlayerStart':
            player.x = obj.x
            player.y = obj.y
            tilemap.update_sprite_position(player)
        elif obj.name == 'Villager':
            villager = Villager(player_anims, obj.x, obj.y)
            villager.name = obj.type
            villagers.append(villager)
            tilemap.add_sprite(villager)
        elif obj.name == 'Tutorial':
            tutorials.append(Tutorial(obj.type, Rect(obj.x, obj.y, obj.x + obj.width, obj.y + obj.height)))

class GameStartScreen(bacon.Game):
    def on_tick(self):
        self.moon = moon.Moon()
        self.moon.x = GAME_WIDTH / 2
        self.moon.y = GAME_HEIGHT / 2
        self.moon.angle = 0.0

        bacon.clear(0, 0, 0, 1)
        bacon.set_color(1, 1, 1, 1)
        self.moon.draw()

        bacon.set_color(1, 0, 0, 1)
        bacon.draw_string(font_ui, 'Monthly Visitor', 
                          0, 0, GAME_WIDTH, GAME_HEIGHT,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.center)

        bacon.set_color(1, 1, 1, 1)
        bacon.draw_string(font_ui, 'Click to start', 
                          0, int(GAME_HEIGHT * 0.75), GAME_WIDTH,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.center)

    def on_mouse_button(self, button, pressed):
        game.screen = None
        game.start()

class GameOverScreen(bacon.Game):
    def __init__(self):
        pass

    def on_tick(self):
        bacon.clear(0, 0, 0, 1)
        bacon.set_color(1, 1, 1, 1)
        bacon.draw_string(font_ui, 'You have died.', 
                          0, 0, GAME_WIDTH, GAME_HEIGHT,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.center)

                         
FULL_MOON_TIME = 30.0
MONTH_TIME = 120.0

lunar_names = [
    'Waxing Gibbous',
    'First Quarter',
    'Waxing Crescent',
    'New Moon',
    'Waning Crescent',
    'Third Quarter',
    'Waning Gibbous',
    'Waning Gibbous',
]

class Game(bacon.Game):
    def __init__(self):
        self.menu = None
        self.screen = GameStartScreen()
        self.tutorial = None

        self.moon = moon.Moon()
        self.moon.x = GAME_WIDTH - 36
        self.moon.y = 36
        self.moon.radius = 32


    def start(self):
        self.lunar_cycle = 0.0
        self.full_moon_time = 0.0
        self.full_moon = False

        self.curtain = 0.0
        player.motive_food = 1.0

    @property
    def lunar_name(self):
        if self.lunar_cycle == 0.0:
            return 'FULL MOON'
        else:
            return lunar_names[int(self.lunar_cycle * 8.0)]

    def on_tick(self):
        update_tweens()

        if self.screen:
            self.screen.on_tick()
            return

        # Lunar cycle
        if self.full_moon:
            self.full_moon_time -= bacon.timestep
            if self.full_moon_time < 0.0:
                self.full_moon = False
                player.end_wolf()
                tween(self, 'curtain', 0.0, 0.3)
        else:
            self.lunar_cycle += bacon.timestep / MONTH_TIME
            if self.lunar_cycle >= 1.0:
                self.lunar_cycle = 0.0
                self.full_moon_time = FULL_MOON_TIME
                self.full_moon = True
                player.start_wolf()
                tween(self, 'curtain', 1.0, 0.3)
                self.menu = None

        # AI
        for animal in animals:
            animal.update_animal_movement()
        for villager in villagers:
            villager.update_villager_movement()

        if not player.is_dying:
            if player.is_wolf:
                player.update_wolf_motives()
            else:
                player.update_player_motives()
                player.update_player_movement()
                player.update_walk_target_movement()

                if not self.full_moon:
                    for factory in factories:
                        factory.update()
        
            if player.motive_food <= 0:
                player.die()


        # Camera
        camera.x = int(player.x)
        camera.y = int(player.y)
        camera.clamp_to_bounds(tilemap.get_bounds())

        # Rendering
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
        bacon.set_color(1, 1, 1, 1)
        inventory.draw()
        
        if self.curtain:
            bacon.set_color(0, 0, 0, 1)
            bacon.fill_rect(0, 0, GAME_WIDTH, self.curtain * 60)
            bacon.fill_rect(0, GAME_HEIGHT, GAME_WIDTH, GAME_HEIGHT - self.curtain * 60)

        bacon.set_color(1, 1, 1, 1)
        self.moon.cycle = self.lunar_cycle
        self.moon.draw()

        self.draw_tutorial()

        bacon.set_color(1, 1, 1, 1)
        #bacon.draw_string(font_ui, 'Lunar: %f' % self.lunar_cycle, GAME_WIDTH, 64, align = bacon.Alignment.right)
        #bacon.draw_string(font_ui, self.lunar_name, GAME_WIDTH, 120, align = bacon.Alignment.right)

        bacon.set_color(1, 1, 1, 1)
        if player.motive_food < player.motive_food_trigger:
            bacon.set_color(1, 0, 0, 1)
        bacon.draw_string(font_ui, 'Strength: %d%%' % round(player.motive_food * 100), GAME_WIDTH, 96, align=bacon.Alignment.right)

        
        if self.menu:
            self.menu.draw()

    def draw_tutorial(self):
        tutorial = None
        for t in tutorials:
            if t.rect.contains(player.x, player.y):
                tutorial = t

        if tutorial != self.tutorial:
            self.tutorial = tutorial
            if tutorial:
                style = bacon.Style(font_ui)
                runs = [bacon.GlyphRun(style, tutorial.text)]
                tutorial.glyph_layout = bacon.GlyphLayout(runs, 32, GAME_HEIGHT - 16, GAME_WIDTH - 64, None, align = bacon.Alignment.center, vertical_align = bacon.VerticalAlignment.bottom)

        if tutorial:
            bacon.set_color(0, 0, 0, 0.8)
            g = tutorial.glyph_layout

            r = Rect(g.x + g.width / 2- g.content_width / 2, g.y, g.x + g.width / 2 + g.content_width / 2, g.y - g.content_height)
            r.fill()
            bacon.set_color(1, 1, 1, 1)
            bacon.draw_glyph_layout(tutorial.glyph_layout)


    def on_key(self, key, pressed):
        if self.screen:
            self.screen.on_key(key, pressed)
            return

        if ENABLE_CHEATS:
            if pressed and key == bacon.Keys.w:
                player.is_wolf = not player.is_wolf
            if pressed and key == bacon.Keys.minus:
                player.motive_food -= 0.2
            if pressed and key == bacon.Keys.plus:
                player.motive_food += 0.2
            if pressed and key == bacon.Keys.right_bracket:
                self.lunar_cycle += 0.25
            if pressed and key == bacon.Keys.left_bracket:
                self.lunar_cycle -= 0.25

    def on_mouse_button(self, button, pressed):
        if self.screen:
            self.screen.on_mouse_button(button, pressed)
            return

        if self.menu:
            self.menu.on_mouse_button(button, pressed)
            return

        if not player.is_wolf and not player.is_dying:
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