from math import floor
import heapq

import bacon
from common import Rect

class Tile(object):
    path_cost = 1
    path_closed = False
    path_parent = None
    path_current = False
    image = None

    def __init__(self, tx, ty, rect, image=None, walkable=True, accept_items=True):
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
    def __init__(self, tile_width, tile_height, cols, rows):
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.cols = cols
        self.rows = rows
        self.tiles = []
        y = 0
        for row in range(rows):
            x = 0
            for col in range(cols):
                self.tiles.append(Tile(col, row, Rect(x, y, x + tile_width, y + tile_height)))
                x += tile_width
            y += tile_height

        # default tile
        self.tiles.append(Tile(-1, -1, Rect(0, 0, 0, 0), walkable=False, accept_items=False))
        self.tiles[-1].can_target = False

    def get_tile_index(self, x, y):
        tx = floor(x / self.tile_width)
        ty = floor(y / self.tile_height)
        if (tx < 0 or tx >= self.cols or
            ty < 0 or ty >= self.rows):
            return len(self.tiles) - 1
        return int(ty * self.cols + tx)

    def get_tile_at(self, x, y):
        return self.tiles[self.get_tile_index(x, y)]

    def get_tile_rect(self, x, y):
        tx = floor(x / self.tile_width)
        ty = floor(y / self.tile_height)
        x = tx * self.tile_width
        y = ty * self.tile_height
        return Rect(x, y, x + self.tile_width, y + self.tile_height)

    def get_bounds(self):
        return Rect(0, 0, self.cols * self.tile_width, self.rows * self.tile_height)

    def draw(self, rect):
        tx1 = max(0, int(floor(rect.x1 / self.tile_width)))
        ty1 = max(0, int(floor(rect.y1 / self.tile_height)))
        tx2 = min(self.cols, int(floor(rect.x2 / self.tile_width)) + 1)
        ty2 = min(self.rows, int(floor(rect.y2 / self.tile_height)) + 1)
        for ty in range(ty1, ty2):
            ti = ty * self.cols + tx1
            for tx in range(tx1, tx2):
                tile = self.tiles[ti]
                if tile.image:
                    r = tile.rect
                    bacon.draw_image(tile.image, r.x1, r.y1, r.x2, r.y2)
                ti += 1

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
