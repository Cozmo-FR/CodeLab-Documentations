import cozmo
from cozmo.lights import blue_light, Color, green_light, Light, red_light, white_light, off_light
import requests, json

LIGHT_COLORS_LIST = [green_light, red_light, blue_light]
COLOR_NAMES_LIST = ['Vert', 'Rouge', 'Bleu']
ANSWER_NAMES_LIST = ['Oui', 'Non', 'Tu ne sais pas']

ANSWER_STATE = 'answer_awaited'
GAME_STATE = 'game'
END_STATE = 'confirmation'

class AkinatorGame:
	"""docstring for AkinatorGame"""
	def __init__(self, robot: cozmo.robot.Robot):
		self._robot = robot
		self.cubes = None
		self.game_state = GAME_STATE
		self.url = 'http://api-fr3.akinator.com/ws/new_session?callback=&partner=1&player=desktopPlayer&constraint='
		self.global_answer = 'Erreur'
		self.step = 0
		self.step2 = 0
		robot.add_event_handler(cozmo.objects.EvtObjectTapped, self.on_cube_tap)

	async def send_akinator_request(self, first_request):

		print("URL REQUEST : " + self.url)

		response = requests.get(self.url)

		if (response.ok):
			parsed = json.loads(response.content)

			if first_request is True:
				'''print(json.dumps(parsed, indent=4))'''
				self.session = parsed['parameters']['identification']['session']
				self.signature = parsed['parameters']['identification']['signature']

				action = self.say_text(parsed['parameters']['step_information']['question'])
				await action.wait_for_completed()

			else:
				action = self.say_text(parsed['parameters']['question'])
				await action.wait_for_completed()

			''' light up cubes to wait for them to be tapped '''
			for x in range(0,3):
				self.cubes[x].set_lights(LIGHT_COLORS_LIST[x])

			self.game_state = ANSWER_STATE

			''' wait for the tap event '''
			await self._robot.world.wait_for(cozmo.objects.EvtObjectTapped)

	async def send_akinator_answer(self):

		url2 = 'http://api-fr3.akinator.com/ws/list?callback=&size=2&max_pic_width=246&max_pic_height=294&pref_photos=VO-OK&mode_question=0'
		url2 = url2 + '&session=' + str(self.session)
		url2 = url2 + '&signature=' + str(self.signature)
		url2 = url2 + '&step=' + str(self.step2)

		print("URL ANSWER : " + url2)

		result = False

		response2 = requests.get(url2)

		if (response2.ok):
			parsed2 = json.loads(response2.content)

			nbObjetsPertinents = int(parsed2['parameters']['NbObjetsPertinents'])
			print("Nombre d'objets pertinents : " + str(nbObjetsPertinents))
			
			if nbObjetsPertinents == 1:
				self.global_answer = parsed2['parameters']['elements'][0]['element']['name']
				result = True
		
			self.step += 1
			self.step2 += 1

		return result

	def say_text(self, text, in_parallel=False):
		print("%s" % text)
		return self._robot.say_text(text, use_cozmo_voice=True, duration_scalar=0.6, voice_pitch=0, in_parallel=in_parallel)

	async def run(self):
		action = self.say_text("Je suis le génie du web, Akinator. Je peux deviner n'importe quel personnage, réel ou fictif. Pour jouer, tape sur le cube vert pour répondre oui, sur le cube rouge pour répondre non et sur le cube bleu si tu ne sais pas. C'est parti !")
		await action.wait_for_completed()
		await self._robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabExcited, ignore_body_track=True).wait_for_completed()

		if not self.cubes_connected():
			print('Cubes did not connect successfully - check that they are nearby. You may need to replace the batteries.')
			return

		first_request = True

		while True:

			await self.send_akinator_request(first_request)

			''' check if only one answer possible '''
			result = await self.send_akinator_answer()

			if result is True:
				await self._robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabThinking).wait_for_completed()
				action = self.say_text("J'ai trouvé ! C'est " + self.global_answer + " !")
				await action.wait_for_completed()
				break

			if first_request is True:
				self.step = 0

			self.url = 'http://api-fr3.akinator.com/ws/answer?callback='
			self.url = self.url + '&session=' + str(self.session)
			self.url = self.url + '&signature=' + str(self.signature)
			self.url = self.url + '&step=' + str(self.step)
			self.url = self.url + '&answer=' + str(self.num_answer)

			first_request = False

		action = self.say_text("Est-ce que j'ai bien deviné ? Vert pour oui, rouge pour non.")
		await action.wait_for_completed()

		''' light up cubes to wait for them to be tapped '''
		for x in range(0,2):
			self.cubes[x].set_lights(LIGHT_COLORS_LIST[x])

		self.game_state = END_STATE

		''' wait for the tap event '''
		await self._robot.world.wait_for(cozmo.objects.EvtObjectTapped)

		if self.win is True:
			print('~COZMO WINS AKINATOR~')
			await self._robot.play_anim_trigger(cozmo.anim.Triggers.PeekABooGetOutHappy).wait_for_completed()
		else:
			print('~COZMO LOSES AKINATOR~')
			await self._robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabLose).wait_for_completed()

	def cubes_connected(self):
		'''Checks if Cozmo connects to all three cubes successfully.

		Returns:
			bool specifying if all three cubes have been successfully connected'''
		cube1 = self._robot.world.get_light_cube(cozmo.objects.LightCube1Id)
		cube2 = self._robot.world.get_light_cube(cozmo.objects.LightCube2Id)
		cube3 = self._robot.world.get_light_cube(cozmo.objects.LightCube3Id)
		self.cubes = [cube1, cube2, cube3]
		self.cube_ids = [cube1.object_id, cube2.object_id, cube3.object_id]
		return not (cube1 == None or cube2 == None or cube3 == None)

	def get_cube_index(self, cube_id):

		i = 0
		for cube in self.cube_ids:
			if cube == cube_id:
				print("Cube " + str(cube) + " tapé, index " + str(i))
				return i
			i += 1
		return 0

	async def on_cube_tap(self, evt, obj, **kwargs):

		'''Responds to cube taps depending on game_state.

		If in ANSWER_STATE, on_cube_tap registers the answer of the player.
		If in END_STATE, on_cube_tap gets if Cozmo won or not.
		'''
		if obj.object_id is not None:
			if self.game_state == ANSWER_STATE:
				self.num_answer = self.get_cube_index(obj.object_id)

			elif self.game_state == END_STATE:
				if self.get_cube_index(obj.object_id) == 0:
					self.win = True
				else:
					self.win = False

			self.game_state = GAME_STATE
			''' turn off the cubes lights '''
			for x in range(0,3):
				self.cubes[x].set_lights(off_light)

async def cozmo_program(robot: cozmo.robot.Robot):
	game = AkinatorGame(robot)
	await game.run()

cozmo.run_program(cozmo_program)