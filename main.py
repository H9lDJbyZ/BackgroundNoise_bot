# -*- coding: utf-8 -*-

import os
import ffmpeg
import requests
import telebot
from telebot import types
import uuid
from dotenv import load_dotenv
load_dotenv()

WHERE = os.getenv('WHERE')
if WHERE == 'local':
    TOKEN = os.getenv('DEV_TOKEN')
else:
    TOKEN = os.getenv('TOKEN')


data_path = "./data"
noise_path = "./noise"
voices_dict = {}
bot = telebot.TeleBot(TOKEN)


def amix(voice, noise):
    in_voice = ffmpeg.input(f'{data_path}/{voice}')
    in_noise = ffmpeg.input(f'{noise_path}/{noise}.opus', stream_loop=-1)
    out = f'{data_path}/out_{noise}_{str(uuid.uuid4())}.opus'
    (
        ffmpeg
        .filter((in_voice, in_noise), "amix", inputs=2, duration="first", dropout_transition=1, normalize=0)
        .output(out, audio_bitrate="128k", format="opus")
        .overwrite_output()
        .run()
    )
    return out


@bot.message_handler(content_types=['voice'])
def add_background(message):
    chat_id = message.chat.id
    voices_dict[chat_id] = message.voice.file_id
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    itembtn1 = types.KeyboardButton('heli ')
    itembtn2 = types.KeyboardButton('bird')
    itembtn3 = types.KeyboardButton('radio')
    # itembtn4 = types.KeyboardButton('exit')
    markup.add(itembtn1, itembtn2, itembtn3)
    bot.send_message(chat_id, "Choose background:", reply_markup=markup)
    bot.register_next_step_handler(message, process_select_noise)


def process_select_noise(message):
    chat_id = message.chat.id
    noise = message.text
    voice_id = voices_dict[chat_id]
    file_info = bot.get_file(voice_id)
    in_filename = f'{voice_id}.opus'
    in_fullfilename = f'{data_path}/{in_filename}'
    file = open(in_fullfilename, "wb")
    file.write(requests.get(f'https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}').content)
    file.close()
    out_fullfilename = amix(in_filename, noise)
    voice = open(out_fullfilename, 'rb')
    bot.send_voice(chat_id, voice)
    voice.close()
    markup = types.ReplyKeyboardRemove(selective=False)
    bot.send_message(chat_id, 'Done.', reply_markup=markup)

    os.remove(in_fullfilename)
    os.remove(out_fullfilename)


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Send me a voice message and I'll add background noise to it.")


@bot.message_handler(commands=['ping'])
def pong(message):
    bot.reply_to(message, f'pong from {WHERE}')


if __name__ == "__main__":
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
