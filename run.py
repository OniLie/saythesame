import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import random
import string
import os

logging.basicConfig(level=logging.INFO)

admin_ids = [int(i) for i in os.getenv('ADMINS_UIDS').split(', ')]

bot = Bot(token=os.getenv('BOT_TOKEN'))

dp = Dispatcher(bot)

menu_text = '📝 Меню'

menu_kb = InlineKeyboardMarkup()
menu_kb.add(InlineKeyboardButton(text='🎲 Створити гру', callback_data='new_game'))
menu_kb.add(InlineKeyboardButton(text='➕ Приєднатися', callback_data='join_game'))

new_menu_kb = InlineKeyboardMarkup()
new_menu_kb.add(InlineKeyboardButton(text='✔ Так', callback_data='new_menu'))
new_menu_kb.add(InlineKeyboardButton(text='✖ Ні', callback_data='delete_message'))


class Player:
    dct = {}

    def __init__(self, uid, name):
        self.id = uid
        self.name = name
        self.message = None
        self.code_waiting = False
        self.in_game = False
        self.answer = None
        Player.dct[self.id] = self

    async def send_message(self, text, parse_mode=None, reply_markup=None):
        await bot.send_message(self.id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)

    async def edit_to_menu(self):
        await self.message.edit_text(menu_text, reply_markup=menu_kb)

    @staticmethod
    def playercheck(message):
        if message.from_user.id in Player.dct:
            player = Player.dct[message.from_user.id]
        else:
            player = Player(uid=message.from_user.id, name=message.from_user.full_name)
        if isinstance(message, types.CallbackQuery):
            player.message = message.message
        else:
            pass
        return player


class Game:
    dct = {}

    def __init__(self, owner: Player):
        self.owner = owner
        self.code = Game.code_generator()
        self.players = []
        self.started = False
        self.answers_count = 0
        self.round = 1
        self.all_answers = []
        self.previos_answers = {}

        asyncio.create_task(self.add_player(self.owner))
        Game.dct[self.code] = self

    @staticmethod
    def code_generator():
        while True:
            code = ''.join(random.choice(string.ascii_uppercase) for i in range(4))
            if code not in Game.dct:
                break
            else:
                pass
            return code

    def waiting_for_players_text(self):
        text = f'Гра {self.code}\n' \
               f'Очікування гравців...\n\n'
        for i in self.players:
            text += f'\n{i.name}'
        return text

    async def waiting_for_players(self):
        text = self.waiting_for_players_text()
        for i in self.players:
            await i.message.edit_text(text=text, reply_markup=self.keyboard(i))

    def waiting_for_answers_text(self):
        text = f'🕹 Гра {self.code} {self.round} раунд\n'
        text += 'Попередні відповіді:' if self.previos_answers else ''
        text += self.answers_text()
        text += '\n\n🗿 Очікування відповідей гравців'
        for i in self.players:
            text += f'\n\n{i.name} {"✅" if i.answer else "✖"}'
        return text

    async def waiting_for_answers(self):
        text = self.waiting_for_answers_text()
        for i in self.players:
            await i.message.edit_text(text=text, reply_markup=self.keyboard(i))

    async def add_player(self, player):
        self.players.append(player)
        player.in_game = self.code
        await self.waiting_for_players()

    def keyboard(self, player):
        kb = InlineKeyboardMarkup()
        if not self.started and player == self.owner:
            kb.add(InlineKeyboardButton(text='✔ Розпочати гру', callback_data=f'start'))
        else:
            pass
        kb.add(InlineKeyboardButton(text='✖ Покинути гру', callback_data=f'leave'))
        return kb

    def answers_text(self):
        text = ''
        for i in self.previos_answers.items():
            text += f'\n{i[0]} – {i[1]}'
        return text

    async def end_game(self):
        self.all_answers.clear()
        text = f'🏆 Гру завершено за {self.round} раундів:\n'
        text += self.answers_text()
        text += f'\n\n🕹 Гра {self.code}'

        self.round = 1
        for i in self.players:
            i.answer = False
            await i.message.edit_text(text=text, reply_markup=self.keyboard(i))

    async def new_round(self):
        self.round += 1
        for i in self.players:
            i.answer = None
        await self.waiting_for_answers()

    async def result(self):
        self.answers_count = 0
        results = [i.answer.capitalize() for i in self.players]
        self.all_answers.extend(results)
        for i in self.players:
            self.previos_answers[i.name] = i.answer
            i.answer = None
        if results.count(results[0]) != len(results):
            await self.new_round()
        else:
            await self.end_game()

    async def start(self):
        await self.waiting_for_answers()

    async def leave(self, player: Player):
        self.players.remove(player)
        player.in_game = None
        player.answer = None
        await player.edit_to_menu()
        if not self.players:
            await self.close()
        else:
            await self.waiting_for_players()

    async def close(self):
        for i in self.players:
            i.in_game = None
            i.answer = None
            await i.edit_to_menu()
        Game.dct.pop(self.code)

    async def answer_init(self, player, answer):
        if answer.capitalize() in self.all_answers:
            await player.send_message(text='❌ Це слово вже було')
        else:
            player.answer = answer
            self.answers_count += 1
            if self.answers_count == len(self.players):
                await self.result()
            else:
                await self.waiting_for_answers()

    async def status_init_single(self, player):
        if self.started:
            await player.message.edit_text(text=self.waiting_for_answers_text(), reply_markup=self.keyboard(player))
        else:
            await player.message.edit_text(text=self.waiting_for_players_text(), reply_markup=self.keyboard(player))


@dp.message_handler(lambda message: message.from_user.id in admin_ids and message.text == '/status')
async def games_status(message: types.Message):
    await message.answer(f'Ігри: {Game.dct}\n\nГравці: {Player.dct}')


@dp.message_handler(commands='start')
async def start(message: types.Message):
    player = Player.playercheck(message)
    if player.message:
        await player.send_message('📝 Створити нове меню в цьому повідомленні?', reply_markup=new_menu_kb)
    else:
        await player.send_message(menu_text, reply_markup=menu_kb)


@dp.callback_query_handler(lambda callback: callback.data == 'delete_message')
async def delete_message(callback: types.CallbackQuery):
    await callback.message.delete()


@dp.callback_query_handler(lambda callback: callback.data == 'new_menu')
async def new_menu_set(callback: types.CallbackQuery):
    player = Player.playercheck(callback)
    player.message = callback.message
    await Game.dct[player.in_game].status_init_single(player)
    await callback.answer()


@dp.callback_query_handler(lambda callback: callback.data == 'join_game')
async def join_init(callback: types.CallbackQuery):
    player = Player.playercheck(callback)
    player.code_waiting = True
    await player.message.edit_text(text='✒ Введіть код гри', reply_markup=menu_kb)
    await callback.answer()


@dp.callback_query_handler(lambda callback: callback.data == 'new_game')
async def create_new_game(callback: types.CallbackQuery):
    player = Player.playercheck(callback)
    Game(owner=player)
    await callback.answer()


@dp.callback_query_handler(lambda callback: callback.data == 'start')
async def start_game(callback: types.CallbackQuery):
    player = Player.playercheck(callback)
    code = player.in_game
    if code not in Game.dct:
        await player.message.edit_text('🫤 Такої гри вже не існує', reply_markup=menu_kb)
    elif Game.dct[code].started:
        await callback.answer('😅 Ця гра вже почалася')
    elif len(Game.dct[code].players) == 1:
        await callback.answer('🥲 Замало гравців. Потрібно щонайменше двоє.')
    else:
        await Game.dct[code].start()
        await callback.answer()


@dp.callback_query_handler(lambda callback: callback.data == 'leave')
async def start_game(callback: types.CallbackQuery):
    player = Player.playercheck(callback)
    code = player.in_game
    if code not in Game.dct:
        await callback.answer('🫤 Такої гри вже не існує')
    elif Game.dct[code].started:
        await callback.answer('😅 Ця гра вже почалася')
    else:
        await Game.dct[code].leave(player)
        await callback.answer()


@dp.message_handler(lambda message: Player.playercheck(message).code_waiting)
async def join_game(message: types.Message):
    player = Player.playercheck(message)
    code = message.text
    if code not in Game.dct:
        await player.message.edit_text('🫤 Такої гри не існує', reply_markup=menu_kb)
    elif Game.dct[code].started:
        await player.message.edit_text('😅 Ця гра вже почалася', reply_markup=menu_kb)
    else:
        await Game.dct[code].add_player(player)
        player.code_waiting = False


@dp.message_handler(lambda message: Player.playercheck(message).in_game and not Player.playercheck(message).answer)
async def set_answer(message: types.Message):
    player = Player.playercheck(message)
    game = Game.dct[player.in_game]
    await game.answer_init(player, message.text)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
