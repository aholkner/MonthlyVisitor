import bacon

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

class Tween(object):
    def __init__(self, obj, attr, start, end, total_time):
        self.obj = obj
        self.attr = attr
        self.total_time = total_time
        self.time = 0.0
        self.start = start
        self.end = end

    def update(self):
        self.time += bacon.timestep
        if self.time >= self.total_time:
            setattr(self.obj, self.attr, self.end)
            tweens.remove(self)
        else:
            setattr(self.obj, self.attr, self.time / self.total_time * (self.end - self.start) + self.start)

tweens = []

def tween(obj, attr, end_value, time):
    for tween in tweens:
        if tween.obj == obj and tween.attr == attr:
            tweens.remove(tween)
            break
    start_value = getattr(obj, attr)
    tweens.append(Tween(obj, attr, start_value, end_value, time))

def update_tweens():
    for tween in list(tweens):
        tween.update()