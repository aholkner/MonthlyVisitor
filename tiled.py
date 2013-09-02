import os.path
import xml.etree.cElementTree as ET

import bacon
import tilemap

class Tileset(object):
    def __init__(self, firstgid, images):
        self.firstgid = firstgid
        self.images = images

def parse_tileset_images(elem, base_dir):
    spacing = int(elem.get('spacing') or 0)
    margin = int(elem.get('margin') or 0)
    tile_width = int(elem.get('tilewidth'))
    tile_height = int(elem.get('tileheight'))
    image = None
    for child in elem:
        if child.tag == 'image':
            filename = child.get('source')
            image = bacon.Image(os.path.join(base_dir, filename))
    
    images = []
    for y in range(margin, image.height - margin, spacing + tile_height):
        for x in range(margin, image.width - margin, spacing + tile_width):
            images.append(image.get_region(x, y, x + tile_width, y + tile_height))

    return images

def parse_tileset(elem, base_dir):
    firstgid = int(elem.get('firstgid'))
    source = elem.get('source')
    if source:
        tree = ET.parse(os.path.join(base_dir, source))
        images = parse_tileset_images(tree.getroot(), base_dir)
    else:
        images = parse_tileset_images(elem, base_dir)
    return Tileset(firstgid, images)

def parse_layer(tm, elem, tilesets):
    name = elem.get('name')
    cols = int(elem.get('width'))
    rows = int(elem.get('height'))

    tx = 0
    ty = 0
    tiles = []
    def add_tile(gid):
        nonlocal tx, ty
        matching_tileset = None
        for tileset in tilesets:
            if gid < tileset.firstgid:
                break
            matching_tileset = tileset

        if matching_tileset:
            image = matching_tileset.images[gid - matching_tileset.firstgid]
            tm.tiles[ty * tm.rows + tx].image = image
        tx += 1
        if tx >= cols:
            tx = 0
            ty += 1

    for child in elem:
        if child.tag == 'data':
            for tile in child:
                if tile.tag == 'tile':
                    add_tile(int(tile.get('gid')))

def parse(tmx_file):
    base_dir = os.path.dirname(tmx_file)

    tree = ET.parse(tmx_file)
    elem = tree.getroot()

    orientation = elem.get('orientation')
    cols = int(elem.get('width'))
    rows = int(elem.get('height'))
    tile_width = int(elem.get('tilewidth'))
    tile_height = int(elem.get('tileheight'))

    tm = tilemap.Tilemap(tile_width, tile_height, cols, rows)
    tilesets = []
    layers = []

    for child in elem:
        if child.tag == 'tileset':
            tilesets.append(parse_tileset(child, base_dir))
        elif child.tag == 'layer':
            parse_layer(tm, child, tilesets)
        
                    
    return tm
