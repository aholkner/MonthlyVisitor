import bacon

bacon.window.title = 'Monthly Visitor'

class Game(bacon.Game):
	def on_tick(self):
		pass

bacon.run(Game())