import os.path
import xml.etree.cElementTree as ET

import bacon

class SpriterFolder(object):
    def __init__(self):
        self.files = []

class SpriterFile(object):
    def __init__(self, name, pivot_x, pivot_y):
        self.name = name
        self.pivot_x = pivot_x
        self.pivot_y = pivot_y

class SpriterData(object):
    def __init__(self):
        self.folders = []
        self.entities = []

def parse_file(data, folder, elem):
    name = elem.get('name')
    pivot_x = float(elem.get('pivot_x'))
    pivot_y = float(elem.get('pivot_y'))
    width = int(elem.get('width'))
    height = int(elem.get('height'))
    file = SpriterFile(name.strip('/'), int(pivot_x * width), height - int(pivot_y * height))
    folder.files.append(file)

def parse_folder(data, elem):
    folder = SpriterFolder()
    data.folders.append(folder)
    for file in elem:
        if file.tag == 'file':
            parse_file(data, folder, file)

def parse(scml_file):
    base_dir = os.path.dirname(scml_file)

    tree = ET.parse(scml_file)
    elem = tree.getroot()
    data = SpriterData()

    for child in elem:
        if child.tag == 'folder':
            parse_folder(data, child)
    return data