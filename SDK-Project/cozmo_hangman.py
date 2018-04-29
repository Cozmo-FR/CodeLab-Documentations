import requests, json
import speech_recognition as sr
import sys
import time
try:
	from PIL import Image, ImageDraw, ImageFont
except ImportError:
	sys.exit("Cannot import from PIL. Do `pip3 install --user Pillow` to install")
import cozmo
from random import randint

# if word definition is required
# parameter = '/' + word
# if similar word is required
# parameter = '/' + word + '/' + similarTo
# if part of the word only is known
# parameter = '/letterPattern=^' + pattern + '$'
# if random word is required
# parameter = '?random=true'

# These are % (sum is 100)
LETTERS_COEFFS = [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 4, 4, 5, 6, 6, 6, 7, 7, 8, 9, 13]
LETTERS_IN_COEFFS_ORDER = ['b', 'j', 'k', 'q', 'v', 'x', 'z', 'f', 'g', 'm', 'p', 'w', 'y', 'c', 'u', 'd', 'l', 'r', 'h', 'n', 's', 'i', 'o', 'a', 't', 'e']
class HangmanGame:

	def __init__(self, robot: cozmo.robot.Robot):
		self._robot = robot
		# if Cozmo gave the word
		self.current_word = ''
		self.current_hangman_word = ''
		self.starter_player = ''
		self.turn_number = 0
		self.letters_list = []
		self.finished = False
		self.last_try_succeed = False

	async def run(self):

		action = self.say_text("We are playing hangman game.")
		await action.wait_for_completed()
		await self.who_starts()

		while self.turn_number <= 8 and not self.finished:
			print('TURN ' + str(self.turn_number))
			await self.hangman_loop()
			self.refresh_screen_word()
			print('SUCCEED: ' + str(self.last_try_succeed))
			if self.turn_number == 0 or not self.last_try_succeed:
				self.turn_number += 1

	async def who_starts(self):

		listened = False
		action = self.say_text("Who starts? You or me?")
		await action.wait_for_completed()
		while not listened:
			result = await self.get_micro_speech_recog()
			if 'you' in result:
				self.starter_player = 'Cozmo'
				action = self.say_text("Okay, I start")
				await action.wait_for_completed()
				listened = True
			elif 'me' in result:
				self.starter_player = 'Player'
				action = self.say_text("Okay, you start")
				await action.wait_for_completed()
				listened = True
			else:
				action = self.say_text("I didn't understand. Can you repeat?")
				await action.wait_for_completed()

	def make_text_image(self, text_to_draw, x, y, font=None):
		'''Make a PIL.Image with the given text printed on it

		Args:
			text_to_draw (string): the text to draw to the image
			x (int): x pixel location
			y (int): y pixel location
			font (PIL.ImageFont): the font to use

		Returns:
			:class:(`PIL.Image.Image`): a PIL image with the text drawn on it
		'''

		# make a blank image for the text, initialized to opaque black
		text_image = Image.new('RGBA', cozmo.oled_face.dimensions(), (0, 0, 0, 255))

		# get a drawing context
		dc = ImageDraw.Draw(text_image)

		# draw the text
		dc.text((x, y), text_to_draw, fill=(255, 255, 255, 255), font=font)

		return text_image

	async def hangman_loop(self):

		if self.turn_number == 0 and self.starter_player == 'Cozmo':
			parameter = '?random=true'
			parsed = await self.send_words_request(parameter)
			self.current_word = parsed['word']

			# TODO: remove, you cheat!
			print("COZMO's WORD is " + self.current_word)

			val = len(self.current_word)
			self.current_hangman_word = ''
			for x in range(0, val):
				if ord(self.current_word[x]) >= 97 and ord(self.current_word[x]) <= 122:
					self.current_hangman_word += '.'
				else:
					self.current_hangman_word += self.current_word[x]

		elif self.turn_number == 0:
			await self.hangman_how_many_letters()

		elif self.turn_number != 8 and self.starter_player == 'Cozmo':
			action = self.say_text("Tell me a letter and I will tell you if it is in my word.")
			await action.wait_for_completed()

			listened = False
			while not listened:
				# pattern: letter = "The letter X"
				letter = await self.get_micro_speech_recog()

				if 'the letter ' in letter and len(letter) == 12:
					letter = letter[-1]
					letter = letter.lower()
					listened = True
				else:
					action = self.say_text("I didn't understand. Can you repeat?")
					await action.wait_for_completed()

			if letter in self.current_word:
				action = self.say_text("It is in my word.")
				await action.wait_for_completed()
				self.last_try_succeed = True

				i = 0
				for c in self.current_word:
					if c == letter:
						word_as_list = list(self.current_hangman_word)
						word_as_list[i] = letter
						self.current_hangman_word = "".join(word_as_list)
					i += 1

				if '.' not in self.current_hangman_word:
					action = self.say_text("Good job! You found the word! It was " + self.current_word)
					await action.wait_for_completed()
					await self._robot.play_anim_trigger(cozmo.anim.Triggers.PeekABooGetOutHappy).wait_for_completed()
					self.finished = True
			else:
				action = self.say_text("It is not in my word.")
				await action.wait_for_completed()
				self.last_try_succeed = False

		elif self.turn_number != 8:

			letter = self.get_random_letter()
			self.letters_list.append(letter)

			action = self.say_text("Is the letter " + letter + " in your word?")
			await action.wait_for_completed()

			listened = False
			while not listened:
				result = await self.get_micro_speech_recog()
				if 'yes' in result:
					await self._robot.play_anim_trigger(cozmo.anim.Triggers.PeekABooGetOutHappy).wait_for_completed()
					self.last_try_succeed = True
					await self.hangman_what_letter_position(letter)

					if '.' not in self.current_hangman_word:
						action = self.say_text("I found the word! It is " + self.current_hangman_word + '!')
						await action.wait_for_completed()
						await self._robot.play_anim_trigger(cozmo.anim.Triggers.PeekABooGetOutHappy).wait_for_completed()
						self.finished = True
					listened = True
				elif 'no' in result:
					await self._robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabFrustrated).wait_for_completed()
					self.last_try_succeed = False
					listened = True
				else:
					action = self.say_text("I didn't understand. Can you repeat?")
					await action.wait_for_completed()

		elif self.starter_player == 'Cozmo':
			action = self.say_text("Sorry, you didn't find in 10 turns. Can you guess the word?")
			await action.wait_for_completed()
			result = await self.get_micro_speech_recog()
			if self.current_word in result:
				action = self.say_text("Good job! You found the word!")
				await action.wait_for_completed()
			else:
				action = self.say_text("Too bad, it was " + self.current_word)
				await action.wait_for_completed()

			self.finished = True

		else:
			parameter = '?letterPattern=^' + self.current_hangman_word + '$'
			parsed = await self.send_words_request(parameter)
			if len(parsed['results']['data']) > 0:
				try_word = parsed['results']['data'][0]
				action = self.say_text("Is your word " + try_word + "?")
				await action.wait_for_completed()

				listened = False
				while not listened:
					result = await self.get_micro_speech_recog()
					if 'yes' in result:
						await self._robot.play_anim_trigger(cozmo.anim.Triggers.PeekABooGetOutHappy).wait_for_completed()
						listened = True
					elif 'no' in result:
						await self._robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabLose).wait_for_completed()
						listened = True
					else:
						action = self.say_text("I didn't understand. Can you repeat?")
						await action.wait_for_completed()

			self.finished = True

	def get_random_letter(self):

		while True:
			letter = LETTERS_IN_COEFFS_ORDER[-1]

			i = 0
			coeffs_sum = int(sum(LETTERS_COEFFS))

			rand_letter = randint(0, coeffs_sum)
			cur_coeffs_sum = 0

			for x in LETTERS_COEFFS:
				if rand_letter <= cur_coeffs_sum:
					# if needed, chr for int to letter and ord for the opposite
					letter = LETTERS_IN_COEFFS_ORDER[i]
					break
				cur_coeffs_sum += x
				i += 1

			if letter not in self.letters_list:
				break

		return letter

	def refresh_screen_word(self):

		duration_s = 2.0

		if not self.last_try_succeed and self.turn_number > 0 and self.turn_number <= 7:
			# ========== DISPLAY HANGMAN IMAGE ==========
			image_name = "hangman_images/hm_" + str(self.turn_number) + ".png"
			image = Image.open(image_name)

			# resize to fit on Cozmo's face screen
			resized_image = image.resize(cozmo.oled_face.dimensions(), Image.BICUBIC)

			# convert the image to the format used by the oled screen
			face_image = cozmo.oled_face.convert_image_to_screen_data(resized_image, invert_image=True)

			self._robot.display_oled_face_image(face_image, duration_s * 1000.0)

			time.sleep(duration_s)

		# ========== DISPLAY WORD TO GUESS ==========
		screen_width, screen_height = cozmo.oled_face.dimensions()
		word_x = 10
		word_y = screen_height / 2

		text_image = self.make_text_image(self.current_hangman_word, word_x, word_y)
		oled_face_data = cozmo.oled_face.convert_image_to_screen_data(text_image)

		# display for 1 second
		self._robot.display_oled_face_image(oled_face_data, duration_s * 1000.0)

	async def hangman_how_many_letters(self):

		succeed = False
		while not succeed:
			action = self.say_text("How many letters does your word have?")
			await action.wait_for_completed()
			word_size = await self.get_micro_speech_recog()
			val = 0

			try:
				val = int(word_size)
				succeed = True
			except ValueError:
				print("That's not an int!")
				action = self.say_text("This is not a number. Please try again.")
				await action.wait_for_completed()

		self.current_hangman_word = ''
		for x in range(0, val):
			self.current_hangman_word += '.'

	async def hangman_what_letter_position(self, letter):

		# used to know if all the occurrences of the letter were given
		succeed = False

		while not succeed:

			action = self.say_text("What is the number of its position in the word?")
			await action.wait_for_completed()

			# used to know if the answer was correctly understood (for the first occurrence)
			listened = False
			while not listened:

				letter_pos = await self.get_micro_speech_recog()
				val = 0

				try:
					val = int(letter_pos) - 1

					if val >= len(self.current_hangman_word):
						print("Word length is too small for this position!")
						action = self.say_text("This number is too big. Please try again.")
						await action.wait_for_completed()
					else:
						word_as_list = list(self.current_hangman_word)
						word_as_list[val] = letter
						self.current_hangman_word = "".join(word_as_list)
						listened = True
				except ValueError:
					print("That's not an int!")
					action = self.say_text("This is not a number. Please try again.")
					await action.wait_for_completed()

			action = self.say_text("Does the letter have another position in the word?")
			await action.wait_for_completed()

			# used to know if the answer was correctly understood (for the other occurrences)
			listened = False
			while not listened:
				result = await self.get_micro_speech_recog()

				if 'yes' in result:
					listened = True
				elif 'no' in result:
					listened = True
					succeed = True
				else:
					action = self.say_text("I didn't understand. Can you repeat?")
					await action.wait_for_completed()

	def say_text(self, text, in_parallel=True):
		print("%s" % text)
		return self._robot.say_text(text, use_cozmo_voice=True, duration_scalar=0.6, voice_pitch=0, in_parallel=in_parallel)
	
	async def get_micro_speech_recog(self):
		# Record Audio
		r = sr.Recognizer()
		with sr.Microphone() as source:
			print("LISTENING TO VOICE: ")
			audio = r.listen(source)
		 
		# Speech recognition using Google Speech Recognition
		try:
			# for testing purposes, we're just using the default API key
			# to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
			# instead of `r.recognize_google(audio)`
			result = r.recognize_google(audio, language="en")
			print("You said: " + result)
			return result

		except sr.UnknownValueError:
			print("Google Speech Recognition could not understand audio")
		except sr.RequestError as e:
			print("Could not request results from Google Speech Recognition service; {0}".format(e))

		return ''

	async def send_words_request(self, parameter):

		url = 'https://wordsapiv1.p.mashape.com/words' + parameter

		#'X-Mashape-Host': 'wordsapiv1.p.mashape.com'
		headers = {'X-Mashape-Key': 'SMVF29KH75mshWDYHcgpf76M3KbXp1q5fREjsnMgxnV3ZgAAtE'}

		response = requests.get(url, headers = headers)
		if (response.ok):

			parsed = json.loads(response.content)
			#print(json.dumps(parsed, indent=4))

			return parsed
		return ''

async def cozmo_program(robot: cozmo.robot.Robot):
	game = HangmanGame(robot)
	await game.run()

cozmo.robot.Robot.drive_off_charger_on_connect = False
cozmo.run_program(cozmo_program)