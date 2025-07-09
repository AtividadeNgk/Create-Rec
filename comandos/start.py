import modules.manager as manager
import modules.recovery_system as recovery_system
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from modules.utils import is_admin

def add_user_to_list(user, bot_id):
   print(user)
   print(bot_id)
   users = manager.get_bot_users(bot_id)
   print(users)
   if not user in users:
       users.append(user)
       manager.update_bot_users(bot_id, users)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
   # ADICIONAR FLAG PARA INDICAR QUE ESTÁ PROCESSANDO START
   context.user_data['processing_start'] = True
   
   # ADICIONAR TIMESTAMP
   import time
   context.user_data['last_start_time'] = time.time()
   
   config = manager.get_bot_config(context.bot_data['id'])
   user_id = str(update.message.from_user.id)
   bot_id = context.bot_data['id']
   
   # ATUALIZA ÚLTIMA ATIVIDADE DO BOT
   manager.update_bot_last_activity(bot_id)
   
   # Adiciona usuário à lista
   add_user_to_list(user_id, bot_id)
   
   # Inicia o sistema de recuperação para este usuário (apenas se não for admin)
   # IMPORTANTE: passa False para não mostrar planos
   if not await is_admin(context, update.message.from_user.id, show_plans_if_not_admin=False):
       recovery_system.start_recovery_for_user(context, user_id, bot_id)
   
   print(config)

   keyboard = [
       [InlineKeyboardButton(config['button'], callback_data='acessar_ofertas')]
   ]
   
   reply_markup = InlineKeyboardMarkup(keyboard)
   
   # Verifica tanto 'midia' quanto 'media' para compatibilidade
   media_config = config.get('midia') or config.get('media')
   if media_config:
       if media_config.get('type') == 'photo':
           await context.bot.send_photo(chat_id=user_id, photo=media_config['file'])
       else:
           await context.bot.send_video(chat_id=user_id, video=media_config['file'])

   if config.get('texto1', False):
       await context.bot.send_message(chat_id=update.message.from_user.id, text=config['texto1'])

   await context.bot.send_message(chat_id=update.message.from_user.id, text=config['texto2'], reply_markup=reply_markup)
   
   # LIMPAR FLAG APÓS PROCESSAR
   context.user_data['processing_start'] = False
   
   return ConversationHandler.END