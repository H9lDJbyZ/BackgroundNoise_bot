# -*- coding: utf-8 -*-

import os
import ffmpeg
import requests
import telebot
from telebot import types
import uuid
import pickle

from dotenv import load_dotenv
load_dotenv()

WHERE = os.getenv('WHERE')
if WHERE == 'local':
    TOKEN = os.getenv('DEV_TOKEN')
else:
    TOKEN = os.getenv('TOKEN')


data_path = "./data"
noise_path = "./noise"
analytic_file = "./analytic.dat"
voices_dict = {}
noises_dict = {}
analytic_dict = {}
bot = telebot.TeleBot(TOKEN)


def load_noises():
    file = open(f'{noise_path}/noise.dat', 'r')
    for line in file:
        listedline = line.strip().split('=')  # split around the = sign
        if len(listedline) > 1:  # we have the = sign in there
            noises_dict[listedline[0]] = listedline[1]
    file.close()


def add_analytic(noise):
    read_analytic()
    if noise in analytic_dict:
        i = int(analytic_dict[noise])
        i += 1
        analytic_dict[noise] = i
    else:
        analytic_dict[noise] = 1
    # with open(analytic_file, 'wb') as f:
    #     pickle.dump(analytic_dict, f)
    file = open(analytic_file, "w")
    for line in analytic_dict:
        file.write(f'{line}={analytic_dict[line]}\n')
    file.close()


def read_analytic():
    if os.path.exists(analytic_file):
        # file = open(analytic_file, 'rb')
        # analytic_dict = pickle.load(file)
        # file.close()
        file = open(analytic_file, 'r')
        for line in file:
            listedline = line.strip().split('=')  # split around the = sign
            if len(listedline) > 1:  # we have the = sign in there
                analytic_dict[listedline[0]] = listedline[1]
        file.close()



def amix(voice, noise):
    in_voice = ffmpeg.input(f'{data_path}/{voice}', )

    noise_filename = f'{noise_path}/{noises_dict[noise]}'
    if not os.path.exists(noise_filename):
        return 'oops'

    # in_noise = (
    #     ffmpeg
    #     .input(noise_filename, stream_loop=-1)
    #     .filter('a', volume=0.5)
    # )
    in_noise = ffmpeg.input(noise_filename, stream_loop=-1)

    out = f'{data_path}/out_{noise}_{str(uuid.uuid4())}.opus'
    (
        ffmpeg
        .filter((in_voice, in_noise), "amix", inputs=2, duration="first", dropout_transition=1, normalize=0)
        .output(out, audio_bitrate="64k", format="opus")
        .overwrite_output()
        .run()
    )
    return out


@bot.message_handler(content_types=['voice'])
def add_background(message):
    chat_id = message.chat.id
    voices_dict[chat_id] = message.voice.file_id
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for n in noises_dict:
        markup.add(n)
    bot.send_message(chat_id, "Choose background:", reply_markup=markup)
    bot.register_next_step_handler(message, process_select_noise)


def process_select_noise(message):
    chat_id = message.chat.id

    markup = types.ReplyKeyboardRemove(selective=False)
    bot.send_message(chat_id, 'wait...', reply_markup=markup)

    noise = message.text
    add_analytic(noise)

    voice_id = voices_dict[chat_id]
    file_info = bot.get_file(voice_id)
    in_filename = f'{voice_id}.opus'
    in_fullfilename = f'{data_path}/{in_filename}'
    file = open(in_fullfilename, "wb")
    file.write(requests.get(f'https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}').content)
    file.close()
    out_fullfilename = amix(in_filename, noise)
    if out_fullfilename == 'oops':
        bot.send_message(chat_id, 'oops')
        return
    voice = open(out_fullfilename, 'rb')
    bot.send_voice(chat_id, voice)
    voice.close()

    os.remove(in_fullfilename)
    os.remove(out_fullfilename)


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Send me a voice message and I'll add background noise to it.")


@bot.message_handler(commands=['ping'])
def pong(message):
    bot.reply_to(message, f'pong from {WHERE}')


@bot.message_handler(commands=['a'])
def a(message):
    read_analytic()
    bot.reply_to(message, str(analytic_dict))


if __name__ == "__main__":
    load_noises()
    read_analytic()
    # for n in noises_dict:
    #     print(n)
    print(analytic_dict)

    if not os.path.exists(data_path):
        os.mkdir(data_path)
    for filename in os.listdir(data_path):
        file_path = os.path.join(data_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
            # elif os.path.isdir(file_path):
            #     shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    bot.enable_save_next_step_handlers(delay=2)
    bot.load_next_step_handlers()
    bot.infinity_polling()
