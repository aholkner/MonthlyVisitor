import logging
logging.basicConfig()

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
ENABLE_CHEATS = False
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

sound_monster = bacon.Sound('res/sound/monster.ogg')
sound_roar = bacon.Sound('res/sound/roar.ogg')
sound_agony1 = bacon.Sound('res/sound/agony1.ogg')
sound_agony2 = bacon.Sound('res/sound/agony2.ogg')
sound_footsteps1 = bacon.Sound('res/sound/footsteps1.ogg')
sound_footsteps2 = bacon.Sound('res/sound/footsteps2.ogg')
sound_crunch1 = bacon.Sound('res/sound/crunch1.ogg')
sound_pickup = bacon.Sound('res/sound/pickup.ogg')
sound_drop = bacon.Sound('res/sound/drop.ogg')
sound_click = bacon.Sound('res/sound/click.ogg')
sound_growl1 = bacon.Sound('res/sound/growl1.ogg')
sound_craft1 = bacon.Sound('res/sound/craft1.ogg')
sound_eat = bacon.Sound('res/sound/eat.ogg')
sound_chime = bacon.Sound('res/sound/chime.ogg')
sound_dawn = bacon.Sound('res/sound/dawn.ogg')
sound_scream = bacon.Sound('res/sound/scream.ogg')
sound_attackfence1 = bacon.Sound('res/sound/attackfence1.ogg')
sound_destroyfence1 = bacon.Sound('res/sound/destroyfence1.ogg')
sound_cow = bacon.Sound('res/sound/cow.ogg')
sound_chicken = bacon.Sound('res/sound/chicken.ogg')
sound_sheep = bacon.Sound('res/sound/sheep.ogg')

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
        anim = Anim([Frame(image, image.width / 2, image.height - 4) for image in images])
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

def load_clothing_anims(name):
    anims = lpc_anims('Clothing-' + name + '.png', 9, 4)
    anims['death'] = spritesheet_anim('Clothing-' + name + '-Death.png', 6, 1, 32, 54)
    return anims

class Frame(object):
    def __init__(self, image, pivot_x, pivot_y):
        self.image = load_image(image)
        self.pivot_x = pivot_x
        self.pivot_y = pivot_y

class Anim(object):
    time_per_frame = 0.5

    def __init__(self, frames):
        self.frames = frames
        
clothing_anims = dict(
    Body = load_clothing_anims('Body'),
    BrownHat = load_clothing_anims('BrownHat'),
    BrownShirt = load_clothing_anims('BrownShirt'),
    BrownShoes = load_clothing_anims('BrownShoes'),
    BrownSkirt = load_clothing_anims('BrownSkirt'),
    ChainHood = load_clothing_anims('ChainHood'),
    ChainTorso = load_clothing_anims('ChainTorso'),
    GreenPants = load_clothing_anims('GreenPants'),
    HairBlonde = load_clothing_anims('HairBlonde'),
    Hood = load_clothing_anims('Hood'),
    MetalBoots = load_clothing_anims('MetalBoots'),
    MetalHat = load_clothing_anims('MetalHat'),
    MetalPants = load_clothing_anims('MetalPants'),
    PurpleJacket = load_clothing_anims('PurpleJacket'),
    WhiteShirt = load_clothing_anims('WhiteShirt'),
    Wolf = load_clothing_anims('Wolf'),
)
default_player_clothing = ['BrownShoes', 'GreenPants', 'WhiteShirt', 'HairBlonde']
naked_player_clothing = ['HairBlonde']
chicken_anims = lpc_anims('Chicken.png', 4, 4)
sheep_anims = lpc_anims('Sheep.png', 4, 4)
cow_anims = lpc_anims('Cow.png', 4, 4)

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
        self.frame_index = 0
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
            self.frame_index = frame_index % len(self.anim.frames)
            self.frame = self.anim.frames[self.frame_index]
        else:
            if self.frame_index < len(self.anim.frames) and frame_index >= len(self.anim.frames):
                self.on_anim_finished()
            self.frame_index = min(frame_index, len(self.anim.frames) - 1)
            self.frame = self.anim.frames[self.frame_index]
            
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
    anim_name = 'idle'
    cooldown = 0
    
    is_wolf = False
    is_dying = False
    motive_food = 1.0
    motive_food_trigger_wolf = 0.8
    motive_food_trigger_human = 0.2
    motive_food_trigger = motive_food_trigger_human
    max_tilemap_path_size = 500
    distance_player_pickup_animal = 24

    distance_wolf_villager_search = GAME_WIDTH * 1.5
    distance_wolf_villager_attack = 32
    target_villager = None
    eating_villager = False
    current_tile = None

    def __init__(self, anims, x, y, clothing=None):
        self._time = 0.0
        self.anims = anims
        self.update_anim()
        self.set_clothing(clothing)

        super(Character, self).__init__(anims[self.anim_name], x, y)
        self.path = None
        self.target_item = None
        
    def set_clothing(self, clothing):
        if clothing:
            self.clothing = [clothing_anims[x] for x in clothing]
        else:
            self.clothing = None

    def draw(self):
        frame = self.frame
        x = int(self.x - frame.pivot_x)
        y = int(self.y - frame.pivot_y)
        bacon.draw_image(frame.image, x, y)

        if self.clothing:
            for layer in self.clothing:
                anim = layer[self.anim_name]
                frame = anim.frames[self.frame_index]
                bacon.draw_image(frame.image, x, y)

        # Update animation for next frame
        self.time += bacon.timestep

    def wait(self, time):
        self.cooldown = max(self.cooldown, time)

    def update_anim(self):
        old_anim_name = self.anim_name
        try:
            self.anim_name = self.action + '_' + self.facing
            self.anim = self.anims[self.anim_name]
        except KeyError:
            self.anim_name = self.action
            self.anim = self.anims[self.anim_name]
        if old_anim_name != self.anim_name:
            self.time = 0

    def die(self):
        if self.is_dying:
            return

        sound_agony2.play()
        self.is_dying = True
        self.action = 'death'
        self.path = None
        self.looping = False
        self.time = 0
        self.update_anim()
        game.menu = None

    def on_anim_finished(self):
        if self.is_dying:
            game.screen = GameOverScreen()

    def walk(self, arrived_func, hueristic_func):
        self.path = tilemap.get_path(tilemap.get_tile_at(self.x, self.y), arrived_func, hueristic_func, self.max_tilemap_path_size)
        if self.path and len(self.path) > 1 and self.path[0].rect.contains(self.x, self.y):
            # Remove first path component if we're already in the tile and past the center of it
            tx0 = self.path[0].rect.center_x
            ty0 = self.path[0].rect.center_y
            tx1 = self.path[1].rect.center_x
            ty1 = self.path[1].rect.center_y
            if dot(self.x - tx0, self.y - ty0, self.x - tx1, self.y - ty1) <= 0:
                del self.path[0]
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
                
        self.update_anim()

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
        self.motive_food = max(self.motive_food - bacon.timestep * 0.002, 0)

    def update_wolf_motives(self):
        self.motive_food = max(self.motive_food - bacon.timestep * 0.015, 0.1)

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
            sound_roar.play()
            sound_agony1.play()

            # Small bite
            self.add_food_motive(0.1)
            spawn_blood(self.x, self.y)
            self.walk_to_waypoint()
            self.wait(0.8)
            return

        if self.cooldown > 0:
            self.cooldown -= bacon.timestep
            self.action = 'idle'
            self.update_anim()
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

                # Couldn't path in direction of any villager, move to nearest waypoint instead
                waypoints.sort(key = lambda v:distance(v, self))
                if self.walk_to_distant_object(waypoints[0]):
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

    def get_behind_tile(self):
        dx = dy = 0
        if self.facing == 'left':
            dx = 32
        elif self.facing == 'right':
            dx = -32
        elif self.facing == 'up':
            dy = 32
        else:
            dy = -32
        return tilemap.get_tile_at(self.x + dx, self.y + dy)
    
class Player(Character):
    run_speed = 320
    naked = False
    footsteps_voice = None
    attack_voice = None

    def set_footsteps(self, sound):
        if self.footsteps_voice:
            if self.footsteps_voice._sound == sound:
                return
            self.footsteps_voice.stop()
            self.footsteps_voice = None
        if sound:
            self.footsteps_voice = bacon.Voice(sound, loop=True)
            self.footsteps_voice.play()
            

    def set_attack_sound(self, sound):
        if self.attack_voice and self.attack_voice.playing:
            return
        self.attack_voice = bacon.Voice(sound)
        self.attack_voice.play()

    def can_walk(self, tile):
        if self.naked and not tile.walkable_entrance:
            # Find owner of this shop, prevent entry if we didn't spawn here
            for villager in villagers:
                if villager.name == tile.entrance_owner:
                    if not villager.spawned_in_shop:
                        return False
        return tile.walkable

    def start_wolf(self):
        sound_monster.play()
        self.motive_food_trigger = self.motive_food_trigger_wolf
        self.is_wolf = True
        self.naked = False
        self.path = None
        self.running = True
        self.action = 'idle'
        self.update_anim()
        self.set_clothing(['Wolf'])
        for item in inventory.items[:]:
            if isinstance(item, Fence):
                item.destroy()
            else:
                inventory.drop(item, self.get_drop_tile())

    def end_wolf(self):
        sound_dawn.play()
        self.motive_food_trigger = self.motive_food_trigger_human
        self.is_wolf = False
        self.path = None
        self.running = False
        self.action = 'idle'
        self.update_anim()
        self.set_clothing(naked_player_clothing)
        self.naked = True
        if self.eating_villager:
            self.on_arrive(tilemap.get_tile_at(self.x, self.y))

        # Check if we're in a shop region, and if so disable the entrance blocker
        # so we can leave
        for villager in villagers:
            if villager.shop_rect and villager.shop_rect.contains(self.x, self.y):
                villager.spawned_in_shop = True
            else:
                villager.spawned_in_shop = False

            # Move villager to center of shop to talk to naked player
            if villager.shop_rect:
                villager.walk_to(villager.shop_rect.center_x, villager.shop_rect.center_y)
    
    def on_collide(self, tile):
        if not tile.walkable_entrance and player.naked:
            game.show_message('"You can\'t come in here like that, get some clothes on!"')
        return super(Player, self).on_collide(tile)

    def on_arrive(self, tile):
        self.action = 'idle'
        if self.eating_villager:
            spawn_blood(self.x, self.y)
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneRibs')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneSkull')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'BoneLegs')
            spawn_item_on_tile(self.get_drop_tile(), 'Bone', 'Bone')
            sound_crunch1.play()
            self.eating_villager = False
            self.add_food_motive(1.0)
            self.wait(2.5)

        # Check if we arrived on an animal
        for animal in animals:
            if animal.can_pick_up and distance(self, animal) < self.distance_player_pickup_animal:
                if not self.target_item and not inventory.is_full:
                    # Only pick up the animal if we weren't targetting anything.
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
    can_pick_up = False

    run_cooldown = 0
    run_cooldown_time = 1.5 # How long to run before exhaustion
    danger_radius = 100

    snare_attract_radius = 512
    snare_catch_radius = 8

    sound = None
    sound_cooldown = -1

    def can_walk(self, tile):
        return tile.walkable and tile.walkable_animal

    def update_animal_movement(self):
        if self.running:
            self.run_cooldown -= bacon.timestep

        self.sound_cooldown -= bacon.timestep

        # Check for getting snared
        for snare in snares:
            if not snare.occupied and snare.rect.contains(self.x, self.y):
                if self.sound:
                    self.sound.play()
                snare.occupied = True
                self.snare = snare
                self.x = snare.x
                self.y = snare.y
                tilemap.update_sprite_position(self)
                tilemap.get_tile_at(self.x, self.y).items.append(self)
                animals.remove(self)
                self.__class__ = self.item_cls
                return

        if not self.path:
            if distance(self, player) < self.danger_radius and self.run_cooldown > 0:
                if self.sound and self.sound_cooldown < 0:
                    self.sound.play()
                    self.sound_cooldown = 5.0
                self.running = True
                self.run_cooldown -= bacon.timestep
                dx = random.randrange(1, 5) * 32
                dy = random.randrange(0, 5) * 32
                if player.x > self.x:
                    dx = -dx
                if player.y > self.y:
                    dy = -dy
                self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]
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
                
                # Check for nearby snares and walk towards
                for snare in snares:
                    if not snare.occupied and distance(snare, self) < self.snare_attract_radius:
                        self.running = False
                        self.path = [tilemap.get_tile_at(snare.x, snare.y)]
                
                # Random walk
                if not self.path:
                    dx = random.randrange(-4, 4) * 32
                    dy = random.randrange(-4, 4) * 32
                    self.wait(random.randrange(1, 8))
                    self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]
            
        self.update_walk_target_movement()


    def on_collide(self, tile):
        self.cooldown = 0.1
        self.run_cooldown = 0


            
class ChickenAnimal(Animal):
    walk_speed = 50
    run_speed = 110
    can_pick_up = True

    run_cooldown = 0
    run_cooldown_time = 1.5 # How long to run before exhaustion
    danger_radius = 100

    snare_attract_radius = 512
    snare_catch_radius = 8

    sound = sound_chicken

class SheepAnimal(Animal):
    walk_speed = 50
    run_speed = 170

    run_cooldown = 0
    run_cooldown_time = 999 # How long to run before exhaustion
    danger_radius = 200

    snare_attract_radius = 512
    snare_catch_radius = 8

    sound = sound_sheep

class CowAnimal(Animal):
    walk_speed = 50
    run_speed = 170

    run_cooldown = 0
    run_cooldown_time = 999 # How long to run before exhaustion
    danger_radius = 200

    snare_attract_radius = 512
    snare_catch_radius = 8

    sound = sound_cow

class Villager(Character):
    walk_speed = 50
    run_speed = 50
    spawned_in_shop = False
    shop_rect = None

    def can_walk(self, tile):
        if not tile.walkable_villager or not tile.walkable_entrance:
            return False
        return tile.walkable and tile.walkable_villager

    def update_villager_movement(self):
        if not self.path:
            if self.cooldown > 0:
                self.cooldown -= bacon.timestep
                return
            if not player.naked:
                dx = random.randrange(-4, 4) * 32
                dy = random.randrange(-4, 4) * 32
                self.path = [tilemap.get_tile_at(self.x + dx, self.y + dy)]
                self.wait(random.randrange(1, 8))
        self.update_walk_target_movement()

    def on_arrive(self, tile):
        super(Villager, self).on_arrive(tile)
        if player.naked:
            self.facing = 'down'
            self.update_anim()


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
    show_durability = False

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
        if self.can_pick_up and not inventory.is_full:
            inventory.pick_up(self, tile)
        else:
            x, y = camera.world_to_view(self.x, self.y)
            show_craft_menu(self, x, y)

    def on_pick_up(self):
        tilemap.remove_sprite(self)

    def on_dropped(self, tile):
        tile.add_item(self)
        tilemap.add_sprite(self)

    def on_used_in_recipe(self, recipe):
        pass

    def on_consumed(self):
        if self.food_human and not player.is_wolf:
            player.add_food_motive(self.food_human)
        elif self.food_wolf and player.is_wolf:
            player.add_food_motive(self.food_wolf)
            player.wait(0.5)
        sound_eat.play()

    def on_attack(self):
        pass


@spawn
class Tree(Item):
    walkable = False
    can_pick_up = False
    anim_name = 'Tree1.png'
    path_cost_wolf = 99999

    def on_used_in_recipe(self, recipe):
        self.anim = object_anims['TreeStump']
        self.__class__ = TreeStump

@spawn
class TreeStump(Item):
    name = 'Tree Stump'
    can_pick_up = False
    
@spawn
class Sapling(Item):
    can_pick_up = False
    anim_name = 'Sapling.png'

@spawn
class BerryPlant(Item):
    name = 'Berry Plant'
    can_pick_up = False

    def on_used_in_recipe(self, recipe):
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
class Reed(Item):
    anim_name = 'Reed.png'

@spawn
class StrangePlant(Item):
    name = 'Rock Flower'
    anim_name = 'StrangePlant.png'
        
@spawn
class VenusFlyTrap(Item):
    pass

@spawn
class SuspiciousHerbs(Item):
    pass

@spawn
class Mushroom(Item):
    food_human = 0.05

@spawn
class Clothes(Item):
    pass

@spawn
class Wood(Item):
    name = 'Wood'

@spawn
class Boulder(Item):
    walkable = False
    can_pick_up = False
    path_cost_wolf = 99999

    def on_used_in_recipe(self, recipe):
        self.destroy()

@spawn
class Rock(Item):
    name = 'Rock'

@spawn
class IronOre(Item):
    name = 'Iron Ore'

@spawn
class IronRock(Item):
    name = 'Iron Rock'
    walkable = False
    can_pick_up = False
    path_cost_wolf = 99999

    def on_used_in_recipe(self, recipe):
        self.destroy()

@spawn
class CoalRock(Item):
    name = 'Coal Rock'
    walkable = False
    can_pick_up = False
    path_cost_wolf = 99999

    def on_used_in_recipe(self, recipe):
        self.destroy()


@spawn
class Coal(Item):
    pass

@spawn
class Bone(Item):
    pass

@spawn
class RawMeat(Item):
    name = 'Raw Meat'
    food_wolf = 0.4

@spawn
class CookedMeat(Item):
    name = 'Cooked Meat'
    food_human = 0.3

@spawn
class Vegetable(Item):
    food_human = 0.05

class Tool(Item):
    show_durability = True
    durability = 1.0
    is_consumed_in_recipe = False
    
    def on_used_in_recipe(self, recipe):
        super(Tool, self).on_used_in_recipe(recipe)
        self.durability -= recipe.tool_durability_effect
        if self.durability <= 0:
            self.destroy()

@spawn
class Pick(Tool):
    pass

@spawn
class Axe(Tool):
    pass

@spawn
class Cleaver(Tool):
    pass

@spawn
class Fire(Item):
    walkable = False
    path_cost_wolf = 99999
    can_pick_up = False

    durability = 1.0
    is_consumed_in_recipe = False
    
    def on_used_in_recipe(self, recipe):
        super(Fire, self).on_used_in_recipe(recipe)
        self.durability -= recipe.tool_durability_effect
        if self.durability <= 0:
            self.__class__ = UsedFire
            self.anim = object_anims['UsedFire']

@spawn
class UsedFire(Item):
    can_pick_up = False

@spawn
class Toadstool(Item):
    pass

@spawn
class Fence(Item):
    walkable = False
    path_cost_wolf = 10
    attackable_wolf = True
    hp = 2.5
    fence_anims = {}

    def on_pick_up(self):
        super(Fence, self).on_pick_up()
        self.update_fence_and_adjacent()

    def on_dropped(self, tile):
        super(Fence, self).on_dropped(tile)
        self.update_fence_and_adjacent()

        # Move player into walkable tile; try backward facing direction first
        tile = player.get_behind_tile()
        if tile.walkable:
            player.x = tile.rect.center_x
            player.y = tile.rect.center_y        
        player.path = []
        tilemap.update_sprite_position(player)
        sound_craft1.play()

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
        player.set_attack_sound(sound_attackfence1)
        self.hp -= bacon.timestep
        if self.hp <= 0:
            sound_destroyfence1.play()
            self.destroy()

@spawn
class StrongFence(Fence):
    name = 'Strong Fence'
    path_cost_wolf = 10
    hp = 5.0
    fence_anims = {}

    
@spawn
class SteelFence(Fence):
    name = 'Steel Fence'
    path_cost_wolf = 10
    hp = 10.0
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
    occupied = None

    def destroy(self):
        if self in snares:
            snares.remove(self)
        return super(Snare, self).destroy()

    def on_dropped(self, tile):
        super(Snare, self).on_dropped(tile)
        snares.append(self)

        # Move player down; try backward facing direction first
        tile = tilemap.get_tile_at(player.x, player.y + 32)
        if tile.walkable:
            player.x = tile.rect.center_x
            player.y = tile.rect.center_y        
        player.path = []
        tilemap.update_sprite_position(player)
        sound_craft1.play()

    def on_pick_up(self):
        try:
            snares.remove(self)
        except ValueError:
            pass

@spawn
class AnimalNet(Snare):
    anim_name = 'Net.png'
    name = 'Animal Net'

class AnimalItem(Item):
    food_wolf = 0.3
    animal_anims = None
    animal_cls = None
    snare = None

    def on_dropped(self, tile):
        animal = self.animal_cls(self.animal_anims, tile.rect.center_x, tile.rect.center_y)
        animal.item_cls = self.__class__
        tilemap.add_sprite(animal)
        animals.append(animal)

    def on_consumed(self):
        if self.snare:
            self.snare.destroy()
            self.snare = None
        spawn_blood(player.x, player.y)
        return super(AnimalItem, self).on_consumed()

    def on_used_in_recipe(self, recipe):
        if self.snare:
            self.snare.destroy()
        spawn_blood(player.x, player.y)
        self.destroy()
        return super(AnimalItem, self).on_used_in_recipe(recipe)


@spawn
class Chicken(AnimalItem):
    animal_cls = ChickenAnimal
    food_wolf = 0.3
    animal_anims = chicken_anims

@spawn
class Sheep(AnimalItem):
    animal_cls = SheepAnimal
    food_wolf = 1.0
    animal_anims = sheep_anims
    can_pick_up = False
    
@spawn
class Cow(AnimalItem):
    animal_cls = CowAnimal
    food_wolf = 1.0
    animal_anims = cow_anims
    can_pick_up = False



class Recipe(object):
    '''
    :param output: class to generate
    :param inputs: dict of class to count
    '''
    sound = sound_craft1

    def __init__(self, output, inputs, text=None, sound=None, tool_durability_effect=0.25, outputs_to_inventory=True):
        if not isinstance(output, collections.Iterable):
            output = [output]
        self.outputs = output
        self.inputs = inputs
        self.text = text
        if output:
            self.name = output[0].__name__
        if sound:
            self.sound = sound
        self.tool_durability_effect = tool_durability_effect
        self.outputs_to_inventory = outputs_to_inventory
          
    def is_input(self, input):
        return input.__class__ in self.inputs

    def is_available(self, extra_item):
        for input, count in self.inputs.items():
            if extra_item and extra_item.__class__ is input:
                count -= 1
            if inventory.get_class_count(input) < count:
                return False
        return True

    def on_craft(self):
        self.sound.play()

class ClothesRecipe(Recipe):
    name = 'Clothes'

    def is_available(self, extra_item):
        if not super(ClothesRecipe, self).is_available(extra_item):
            return False
        if not player.naked:
            return False
        return True

    def on_craft(self):
        player.set_clothing(default_player_clothing)
        player.naked = False

recipes = [
    Recipe([Wood, Wood, Wood], {Axe: 1, Tree: 1}, 'Chop down for wood', tool_durability_effect=0.25, outputs_to_inventory=False),
    Recipe([Coal], {Pick: 1, CoalRock: 1}, 'Mine for coal', tool_durability_effect=0.25),
    Recipe([IronOre, IronOre, IronOre], {Pick: 1, IronRock: 1}, 'Mine for iron ore', tool_durability_effect=0.25, outputs_to_inventory=False),
	Recipe([Rock, Rock], {Pick: 1, Boulder: 1}, 'Smash boulder', tool_durability_effect=0.5, outputs_to_inventory=False),
    Recipe([Iron], {Pick: 1, IronOre: 2}, 'Forge Iron', tool_durability_effect=0.25),
    Recipe(Axe, {Stick: 1, Rock: 1}),
    Recipe(Pick, {Stick: 1, Iron: 1}),
    Recipe(Steel, {Fire: 1, Iron: 1, Coal: 1}, tool_durability_effect=0.2),
    Recipe(Cleaver, {Stick: 1, Steel: 1}),
    Recipe(Fire, {Wood: 2, Coal: 1}, outputs_to_inventory=False),
    Recipe(Fence, {Wood: 2}),
    Recipe(StrongFence, {Fence: 1, Wood: 2}),
    Recipe(SteelFence, {Steel: 4}),
    Recipe(RawMeat, {Chicken: 1}, 'Kill for meat', sound=sound_scream),
    Recipe([RawMeat, RawMeat], {Sheep: 1, Cleaver: 1}, 'Kill for meat', sound=sound_scream, tool_durability_effect=0.25),
    Recipe([RawMeat, RawMeat, RawMeat], {Cow: 1, Cleaver: 1}, 'Kill for meat', sound=sound_scream, tool_durability_effect=0.25),
    Recipe(CookedMeat, {Fire: 1, RawMeat: 1}, 'Cook meat', sound=sound_pickup, tool_durability_effect=0.5),
    #Recipe(Snare, {Rope: 2, Vegetable: 1}),
    Recipe(AnimalNet, {Rope: 2, Rock: 2, Vegetable: 1}),
    Recipe(Rope, {Grass: 3}),
    Recipe(Stick, {Sapling: 1}, "Break off stick", sound=sound_pickup),
    Recipe(Berries, {BerryPlant: 1}, 'Pick berries', sound=sound_pickup),
    ClothesRecipe([], {Clothes: 1}, 'Wear clothes'),

]

def path_arrived(destination):
    def func(tile):
        return tile is destination
    return func

def path_heuristic_player(destination):
    def func(tile):
        if not tile.walkable and tile is not destination:
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
    def __init__(self, tile, spawn_class_name, owner=None, cooldown_time=70):
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
    def __init__(self, recipe, extra_item):
        self.x = 0
        self.y = 0
        self.lines = []
        style = bacon.Style(font_ui)
        for (cls, count) in recipe.inputs.items():
            satisfied_count = count
            if extra_item and isinstance(extra_item, cls):
                satisfied_count -= 1
            satisfied = inventory.get_class_count(cls) >= satisfied_count
            text = '[%s] %dx %s' % ('X' if satisfied else ' ', count, cls.get_name())
            run = bacon.GlyphRun(style, text)
            self.lines.append(bacon.GlyphLayout([run], 0, 0, width=280, height=None, align=bacon.Alignment.left, vertical_align=bacon.VerticalAlignment.bottom))
        self.layout()
        self.content_width = max(line.content_width for line in self.lines)


class MenuTextHint(MenuHint):
    def __init__(self, text):
        self.x = 0
        self.y = 0
        self.lines = []
        style = bacon.Style(font_ui)
        run = bacon.GlyphRun(style, text)
        self.lines.append(bacon.GlyphLayout([run], 0, 0, width=280, height=None, align=bacon.Alignment.left, vertical_align=bacon.VerticalAlignment.bottom))
        self.layout()
        self.content_width = self.lines[0].content_width

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
            if self.rect.x2 + self.hint.content_width < GAME_WIDTH:
                self.hint.x = self.rect.x2
            else:
                self.hint.x = self.rect.x1 - self.hint.content_width
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
             
class PickUpAction(object):
    def __init__(self, item, tile):
        self.item = item
        self.tile = tile

    def __call__(self):
        inventory.pick_up(self.item, self.tile)

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
            hint = MenuRecipeHint(recipe, extra_item)
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
        if isinstance(item, Fence) and tile is tilemap.get_tile_at(player.x, player.y):
            # Ensure position behind player is free if drop tile is player
            if not player.get_behind_tile().walkable:
                tile = None
        if tile:
            game.menu.add('Drop %s' % item.get_name(), DropAction(item))
        else:
            game.menu.add('Drop %s' % item.get_name(), disabled=True)
    elif item.can_pick_up:
        if inventory.is_full:
            game.menu.add('Pick up %s' % item.get_name(), disabled=True, hint=MenuTextHint('Inventory full'))
        else:
            game.menu.add('Pick up %s' % item.get_name(), PickUpAction(item, tilemap.get_tile_at(item.x, item.y)))
    
    if not game.menu.items:
        game.menu = None
    else:
        sound_click.play()


class Inventory(object):
    slots = 6
    slot_image = load_image('InventorySlot.png')
    def __init__(self):
        self.items = []
        self.item_size_x = 44
        self.x = int(GAME_WIDTH / 2 - self.slots * self.item_size_x / 2)
        self.y = GAME_HEIGHT - 32
        
    @property
    def is_full(self):
        return len(self.items) >= self.slots

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
        if self.is_full:
            return
        tile.remove_item(item)
        item.on_pick_up()
        self.add_item(item)
        self.layout()
        sound_pickup.play()
        
    def add_item(self, item):
        if self.is_full:
            tile = player.get_drop_tile()
            if tile:
                item.on_dropped(tile)
        else:
            self.items.append(item)
            self.layout()

    def drop(self, item, tile):
        self.items.remove(item)
        if tile:
            item.on_dropped(tile)
        self.layout()
        sound_drop.play()

    def remove(self, item):
        self.items.remove(item)
        self.layout()
        
    def craft(self, recipe, initial_item):
        if initial_item in self.items:
            slot_index = self.items.index(initial_item)
        else:
            slot_index = len(self.items)
        new_items = []
        for output in recipe.outputs:
            crafted_item = output(output.get_default_anim(), 0, 0)
            self.items.insert(slot_index, crafted_item)
            if recipe.outputs_to_inventory:
                new_items.append(crafted_item)
            else:
                self.drop(crafted_item, player.get_drop_tile())

        for item_class, count in recipe.inputs.items():
            for i in range(count):
                if initial_item and initial_item.__class__ is item_class:
                    if initial_item.is_consumed_in_recipe:
                        if initial_item in self.items:
                            self.items.remove(initial_item)
                    initial_item.on_used_in_recipe(recipe)
                    initial_item = None
                else:
                    for item in self.items:
                        if item.__class__ is item_class:
                            if item.is_consumed_in_recipe:
                                self.items.remove(item)
                            item.on_used_in_recipe(recipe)
                            break

        while len(self.items) > self.slots:
            if new_items:
                self.drop(new_items[-1], player.get_drop_tile())
                del new_items[-1]
            else:
                self.drop(self.items[-1], player.get_drop_tile())

        recipe.on_craft()
        self.layout()

    def draw(self):
        bacon.set_color(1, 1, 1, 1)
        for i in range(self.slots):
            bacon.draw_image(self.slot_image, self.x + i * self.item_size_x - self.slot_image.width / 2, self.y - self.slot_image.height / 2)
        for item in self.items:
            if item.show_durability:
                bacon.set_color(0.5, 0, 0, 1.0)
                Rect(item.x - 16, item.y + 16, item.x - 16 + 32 * item.durability, item.y + 18).fill()
                bacon.set_color(1, 1, 1, 1)
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
object_anims['Fire'] = spritesheet_anim('Item-Fire.png', 1, 4, 16, 16)
object_anims['Fire'].time_per_frame = 0.1

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
                if props['Anim'] not in object_anims:
                    object_anims[props['Anim']] = Anim([Frame(image, 16, 16)])
            if 'Class' in props:
                _spawn_classes[props['Class']].inventory_image = image
            if 'Fence' in props:
                fmt = props['Fence']
                Fence.fence_anims[fmt] = Anim([Frame(image, 16, 16)])
            if 'StrongFence' in props:
                fmt = props['StrongFence']
                StrongFence.fence_anims[fmt] = Anim([Frame(image, 16, 16)])
            if 'SteelFence' in props:
                fmt = props['SteelFence']
                SteelFence.fence_anims[fmt] = Anim([Frame(image, 16, 16)])
            if 'Blood' in props:
                blood_images.append(image)
            if 'BloodDribble' in props:
                blood_dribble_images.append(image)

Fence.fence_anims[''] = Fence.get_default_anim()
StrongFence.fence_anims[''] = StrongFence.get_default_anim()
SteelFence.fence_anims[''] = SteelFence.get_default_anim()

class Tutorial(object):
    shown = False
    def __init__(self, text, rect):
        self.text = text
        self.rect = rect

player = Player(clothing_anims['Body'], 0, 0, default_player_clothing)
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
                    animal = ChickenAnimal(chicken_anims, tile.rect.center_x, tile.rect.center_y)
                    animal.item_cls = Chicken
                    animals.append(animal)
                    tilemap.add_sprite(animal)
                elif class_name == 'Sheep':
                    animal = SheepAnimal(sheep_anims, tile.rect.center_x, tile.rect.center_y)
                    animal.item_cls = Sheep
                    animals.append(animal)
                    tilemap.add_sprite(animal)
                elif class_name == 'Cow':
                    animal = CowAnimal(cow_anims, tile.rect.center_x, tile.rect.center_y)
                    animal.item_cls = Cow
                    animals.append(animal)
                    tilemap.add_sprite(animal)
                elif class_name:
                    spawn_item_on_tile(tile, class_name, anim_name)
                
                factory_class = image.properties.get('FactoryClass')
                if factory_class:
                    owner = image.properties.get('Owner')
                    cooldown = int(image.properties.get('Cooldown', 70))
                    factories.append(Factory(tile, factory_class, owner, cooldown))

                if image.properties.get('Waypoint'):
                    waypoint = Waypoint(tile.rect.center_x, tile.rect.center_y)
                    waypoints.append(waypoint)
    elif layer.name == 'Blood':
        blood_layer = layer
camera = Camera()


villager_clothing = dict(
    Baker = ['BrownSkirt', 'WhiteShirt'],
    Butcher = ['BrownShoes', 'GreenPants', 'PurpleJacket', 'Hood'],
    Tailor = ['BrownShoes', 'BrownSkirt', 'WhiteShirt', 'HairBlonde'],
    Carpenter = ['MetalBoots', 'BrownSkirt', 'ChainTorso', 'MetalHat'],
    Blacksmith = ['MetalBoots', 'MetalPants', 'ChainTorso', 'ChainHood'],
    Farmer = ['GreenPants', 'MetalHat']
)

for object_layer in tilemap.object_layers:
    for obj in object_layer.objects:
        if obj.name == 'PlayerStart':
            player.x = obj.x
            player.y = obj.y
            tilemap.update_sprite_position(player)
        elif obj.name == 'Villager':
            villager = Villager(clothing_anims['Body'], obj.x, obj.y, villager_clothing.get(obj.type))
            villager.name = obj.type
            villagers.append(villager)
            tilemap.add_sprite(villager)
        elif obj.name == 'Tutorial':
            tutorial = Tutorial(obj.type, Rect(obj.x, obj.y, obj.x + obj.width, obj.y + obj.height))
            tutorial.condition = obj.properties.get('Condition')
            tutorial.owner = obj.properties.get('Owner')
            tutorials.append(tutorial)
        elif obj.name == 'ShopRegion':
            for villager in villagers:
                if villager.name == obj.type:
                    villager.shop_rect = Rect(obj.x, obj.y, obj.x + obj.width, obj.y + obj.height)
            

class GameStartScreen(bacon.Game):
    def __init__(self):
        sound_growl1.play()

    def on_tick(self):
        self.moon = moon.Moon()
        self.moon.x = GAME_WIDTH / 2
        self.moon.y = GAME_HEIGHT / 2
        self.moon.angle = 0.0

        bacon.clear(0, 0, 0, 1)
        bacon.set_color(0.6, 0.6, 0.6, 1.0)
        self.moon.draw()

        bacon.set_color(1, 0, 0, 1)
        bacon.draw_string(font_ui, 'Monthly Visitor', 
                          0, 0, GAME_WIDTH, GAME_HEIGHT,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.center)

        bacon.set_color(1, 1, 1, 1)
        bacon.draw_string(font_ui, 'A game by Alex Holkner and Amanda Schofield', 
                          0, GAME_HEIGHT / 2 + 24, GAME_WIDTH,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.center)

        bacon.set_color(1, 1, 1, 1)
        bacon.draw_string(font_ui, 'Click to start', 
                          0, GAME_HEIGHT - 4, GAME_WIDTH,
                          align = bacon.Alignment.center,
                          vertical_align = bacon.VerticalAlignment.bottom)

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
MONTH_TIME = 180.0

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

        self.message = None
        self.message_time = 0.0
        self.tutorial_food_trigger = False
        self.tutorial_full_moon = False
        self.tutorial_end_full_moon = False

        self.game_time = 0

    def start(self):
        self.lunar_cycle = 0.0
        self.full_moon_time = 0.0
        self.full_moon = False

        self.curtain = 0.0
        player.motive_food = 1.0
        sound_dawn.play()

    @property
    def lunar_name(self):
        if self.lunar_cycle == 0.0:
            return 'FULL MOON'
        else:
            return lunar_names[int(self.lunar_cycle * 8.0)]

    def on_tick(self):
        self.game_time += bacon.timestep
        update_tweens()

        if self.screen:
            self.screen.on_tick()
            return

        if self.message_time > 0.0:
            self.message_time -= bacon.timestep
        else:
            self.message = None

        # Lunar cycle
        if not player.is_dying:
            if self.full_moon:
                self.full_moon_time -= bacon.timestep
                if self.full_moon_time < 0.0:
                    if not self.tutorial_end_full_moon:
                        self.show_message("What happened?? Where am I?")
                        self.tutorial_end_full_moon = True
                    self.full_moon = False
                    player.end_wolf()
                    tween(self, 'curtain', 0.0, 0.3)
            else:
                self.lunar_cycle += bacon.timestep / MONTH_TIME
                if self.lunar_cycle >= 0.95 and not self.tutorial_full_moon:
                    self.show_message("The moon... is calling to me.  I can feel a change... within me...")
                    self.tutorial_full_moon = True
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
                #player.update_player_movement()
                player.update_walk_target_movement()

                if not self.full_moon:
                    for factory in factories:
                        factory.update()
        
            if player.motive_food <= 0:
                player.die()

            if player.action == 'walk':
                if player.is_wolf:
                    player.set_footsteps(sound_footsteps2)
                else:
                    player.set_footsteps(sound_footsteps1)
                    player.footsteps_voice.gain = 0.3
            else:
                player.set_footsteps(None)

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
                
        bacon.set_color(0, 0, 1, 1)
        #tilemap.get_tile_rect(player.x, player.y).draw()
        
        bacon.set_color(1, 0, 0, 1)
        
        #tilemap.get_bounds().draw()
        
        
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
            if not self.tutorial_food_trigger and not player.is_wolf:
                game.show_message("I'm so... hungry... must find something to eat!")
                self.tutorial_food_trigger = True
            if int(self.game_time * 4) % 2 == 0:
                bacon.set_color(0, 0, 0, 0)
        
        stamina_size = 86
        bacon.draw_string(font_ui, 'Stamina', GAME_WIDTH - 2, 96, align=bacon.Alignment.right)
        bacon.set_color(0.7, 0.7, 0.7, 1.0)
        x = GAME_WIDTH - stamina_size - 4
        y = 104
        Rect(x - 2, y - 2, x + stamina_size + 2, y + 4).fill()
        bacon.set_color(0.4, 0, 0, 1.0)
        Rect(x, y, x + stamina_size * player.motive_food, y + 2).fill()
        
        
        if self.menu:
            self.menu.draw()

    def draw_tutorial(self):
        tutorial = None
        for t in tutorials:
            if not player.is_wolf and t.rect.contains(player.x, player.y):
                if t.condition == 'Naked' and not player.naked:
                    continue
                if t.owner:
                    if len([v for v in villagers if v.name == t.owner]) == 0:
                        continue
                tutorial = t
                break

        if self.message:
            tutorial = self.message

        if tutorial != self.tutorial:
            if self.tutorial and self.tutorial in tutorials:
                tutorials.remove(self.tutorial)

            self.tutorial = tutorial
            if tutorial:
                sound_chime.play()
                style = bacon.Style(font_ui)
                runs = [bacon.GlyphRun(style, tutorial.text)]
                tutorial.glyph_layout = bacon.GlyphLayout(runs, 32, GAME_HEIGHT - 64, GAME_WIDTH - 64, None, align = bacon.Alignment.center, vertical_align = bacon.VerticalAlignment.bottom)

        if tutorial:
            bacon.set_color(0, 0, 0, 0.8)
            g = tutorial.glyph_layout

            r = Rect(g.x + g.width / 2- g.content_width / 2, g.y, g.x + g.width / 2 + g.content_width / 2, g.y - g.content_height)
            r.fill()
            bacon.set_color(1, 1, 1, 1)
            bacon.draw_glyph_layout(tutorial.glyph_layout)

    def show_message(self, message, time=5.0):
        self.message = Tutorial(message, None)
        game.message_time = time

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
                if self.full_moon:
                    self.full_moon_time = 0
                else:
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