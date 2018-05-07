from epics import PV

class MegampSet():

	module = 0
	channel = 0
	modlist = []
	
	def __init__(self):
		print("I: init MegampSet")
		self.refresh()

	def refresh(self):
		pv = PV('MEGAMP:MOD:SEL', connection_timeout=2)
		self.modlist = pv.enum_strs

	def setModule(self, mod):
		if mod in self.modlist:
			self.module = mod
		else:
			raise IndexError
	
	def getModule(self):
		return self.module

	def setChannel(self, ch):
		if (int(ch) >= 0) and (int(ch) <= 15):
			self.channel = ch
		else:
			raise IndexError

	def getChannel(self):
		return self.channel

	def getModlist(self):
		return self.modlist