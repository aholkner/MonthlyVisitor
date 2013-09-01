import tilemap
import xml.etree.cElementTree as ET

def parse(tmx_file):
    tree = ET.parse(tmx_file)
    map = tree.getroot()

    orientation = map.get('orientation')
    cols = int(map.get('width'))
    rows = int(map.get('height'))
    tile_width = int(map.get('tilewidth'))
    tile_height = int(map.get('tileheight'))

    tm = tilemap.Tilemap(tile_width, tile_height, cols, rows)
    return tm
