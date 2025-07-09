import modules.manager as manager
import modules.payment as payment
import modules.utils as utils
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, Updater, CallbackContext, ChatJoinRequestHandler
from telegram.error import BadRequest, Conflict
import asyncio, json

from modules.utils import escape_markdown_v2

async def send_disparo(context, user_id, config):
    
    try:
        print(user_id)
        keyboard = []
        if config['tipo'] == "plano":
            payment_id = manager.create_payment(user_id, config['plano'], config['plano'], context.bot_data['id'])
            valor = config['plano']['value']
            keyboard = [
                [InlineKeyboardButton('💠 Pagar via PIX 💠', callback_data=f'exibir_{payment_id}')]
            ]
        elif config['tipo'] == "livre":
            keyboard = [[InlineKeyboardButton('Acessar Conteúdo', url=config['link'])]]
            
        reply_markup=InlineKeyboardMarkup(keyboard)
        
        if config['mensagem'].get('media', False):
            if config['mensagem'].get('text', False):
                print(config['mensagem'].get('media', False))
                if config['mensagem']['media'].get('type', False) == 'photo':
                    await context.bot.send_photo(chat_id=user_id, photo=config['mensagem']['media']['file'], caption=config['mensagem'].get('text', False), reply_markup=reply_markup)
                else:
                    await context.bot.send_video(chat_id=user_id, video=config['mensagem']['media']['file'], caption=config['mensagem'].get('text', False), reply_markup=reply_markup)
            else:
                print('sem texto')
                if config['mensagem']['media'].get('type') == 'photo':
                    await context.bot.send_photo(chat_id=user_id, photo=config['mensagem']['media']['file'], reply_markup=reply_markup)
                else:
                    await context.bot.send_video(chat_id=user_id, video=config['mensagem']['media']['file'], reply_markup=reply_markup)
        else:
            print('texto')
            await context.bot.send_message(chat_id=user_id, text=config['mensagem']['text'], reply_markup=reply_markup)
    except Exception as e:
        print(e)

        return False
    return True

def send_payment():
    pass

async def recovery_thread(context, user_id, config, id):
    # Esta função não é mais usada com o novo sistema
    # Mantida apenas para compatibilidade
    pass

async def send_upsell(context, user_id):
    """Envia o upsell como oferta de PIX direto"""
    # Marca que está no fluxo de upsell
    context.user_data['in_upsell_flow'] = True
    
    config = manager.get_bot_upsell(context.bot_data['id'])
    
    if not config or not config.get('value') or not config.get('group_id'):
        # Se não tem upsell configurado, limpa a flag e retorna
        context.user_data['in_upsell_flow'] = False
        return
    
    # Cria um pagamento para o upsell
    upsell_plan = {
        'name': 'Upsell - Grupo VIP Extra',
        'value': config['value'],
        'time_type': 'eterno',
        'time': 'eterno',
        'is_upsell': True,
        'upsell_group': config['group_id']
    }
    
    payment_id = manager.create_payment(str(user_id), upsell_plan, 'Upsell', context.bot_data['id'])
    
    keyboard = [
        [
            InlineKeyboardButton('✅ 𝗔𝗰𝗲𝗶𝘁𝗮𝗿', callback_data=f'upsell_aceitar_{payment_id}'),
            InlineKeyboardButton('❌ Recusar', callback_data=f'upsell_recusar_{payment_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia a mensagem do upsell
    if config.get('media') and config['media']:
        if config.get('text'):
            if config['media']['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=config['media']['file'],
                    caption=config['text'],
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=config['media']['file'],
                    caption=config['text'],
                    reply_markup=reply_markup
                )
        else:
            if config['media']['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=config['media']['file'],
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=config['media']['file'],
                    reply_markup=reply_markup
                )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=config.get('text', f'Por apenas R$ {config["value"]} tenha acesso ao nosso grupo VIP exclusivo!'),
            reply_markup=reply_markup
        )

async def send_downsell(context, user_id):
    """Envia o downsell se recusar o upsell"""
    config = manager.get_bot_downsell(context.bot_data['id'])
    upsell_config = manager.get_bot_upsell(context.bot_data['id'])
    
    if not config or not config.get('value'):
        # Se não tem downsell configurado, não faz nada
        return
    
    # Cria um pagamento para o downsell (usa o mesmo grupo do upsell)
    downsell_plan = {
        'name': 'Downsell - Oferta Especial',
        'value': config['value'],
        'time_type': 'eterno',
        'time': 'eterno',
        'is_downsell': True,
        'downsell_group': upsell_config['group_id']  # Mesmo grupo do upsell
    }
    
    payment_id = manager.create_payment(str(user_id), downsell_plan, 'Downsell', context.bot_data['id'])
    
    keyboard = [
        [
            InlineKeyboardButton('✅ 𝗔𝗰𝗲𝗶𝘁𝗮𝗿 𝗢𝗳𝗲𝗿𝘁𝗮', callback_data=f'downsell_aceitar_{payment_id}'),
            InlineKeyboardButton('❌ Continuar sem', callback_data=f'downsell_recusar_{payment_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia a mensagem do downsell
    if config.get('media') and config['media']:
        if config.get('text'):
            if config['media']['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=config['media']['file'],
                    caption=config['text'],
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=config['media']['file'],
                    caption=config['text'],
                    reply_markup=reply_markup
                )
        else:
            if config['media']['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=config['media']['file'],
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=config['media']['file'],
                    reply_markup=reply_markup
                )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=config.get('text', f'Última chance! Por apenas R$ {config["value"]} tenha acesso ao grupo VIP!'),
            reply_markup=reply_markup
        )

async def send_expiration(context, user_id):
    config = manager.get_bot_expiration(context.bot_data['id'])
    if not config.get('text', False) or not config.get('media', False):
        return
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text='RENOVAR ASSINATURA', callback_data='acessar_ofertas')]])
    if config.get('media', False):
        if config.get('text', False):
            if config['media'].get('type') == 'photo':
                await context.bot.send_photo(chat_id=user_id, photo=config['media']['file'], caption=config['text'], reply_markup=reply_markup)
            else:
                await context.bot.send_video(chat_id=user_id, video=config['media']['file'], caption=config['text'], reply_markup=reply_markup)
        else:
            if config['media'].get('type') == 'photo':
                await context.bot.send_photo(chat_id=user_id, photo=config['media']['file'], reply_markup=reply_markup)
            else:
                await context.bot.send_video(chat_id=user_id, video=config['media']['file'], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=config['text'], reply_markup=reply_markup)

async def send_invite(context, user_id):
    try:
        # Carrega as informações do grupo
        grupo_info = manager.get_bot_group(bot_id=context.bot_data['id'])
        user = await context.bot.get_chat(user_id)
        # Cria o link de convite com solicitação de entrada ativada
        
        
        group_invite_link = await context.bot.create_chat_invite_link(
            chat_id=grupo_info, 
            creates_join_request=True
        )
        nickname = user.username
        keyboard = [
            [InlineKeyboardButton("ENTRAR NO GRUPO", url=group_invite_link.invite_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Pagamento aprovado! Clique no botão abaixo para entrar no grupo.",
            reply_markup=reply_markup
        )
        print(f"[INFO] Link de convite criado com sucesso: {group_invite_link.invite_link}")
    except ValueError as ve:
        print(f"[ERRO] Erro no ID do grupo: {ve}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Não foi possível identificar o grupo. Por favor, entre em contato com o suporte."
        )
    except Exception as e:
        print(f"[ERRO] Erro ao criar link de grupo: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ocorreu um erro ao gerar o link de convite. Por favor, tente novamente mais tarde."
        )

async def acessar_planos(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    planos = manager.get_bot_plans(context.bot_data['id'])
    keyboard_plans = []
    for plan_index in range(len(planos)):
        keyboard_plans.append([InlineKeyboardButton(f'{planos[plan_index]['name']} - R$ {planos[plan_index]['value']}', callback_data=f"plano_{plan_index}")])
    reply_markup = InlineKeyboardMarkup(keyboard_plans)
    await query.message.edit_text('Escolha uma oferta abaixo:', parse_mode='HTML', reply_markup=reply_markup)
    
async def acessar_planos_mensagem(update: Update, context: CallbackContext):
    """Versão de acessar_planos para mensagens diretas (não callback)"""
    # Não tem query.answer() porque não é um callback
    
    planos = manager.get_bot_plans(context.bot_data['id'])
    keyboard_plans = []
    for plan_index in range(len(planos)):
        keyboard_plans.append([InlineKeyboardButton(f'{planos[plan_index]['name']} - R$ {planos[plan_index]['value']}', callback_data=f"plano_{plan_index}")])
    reply_markup = InlineKeyboardMarkup(keyboard_plans)
    
    # Envia uma nova mensagem ao invés de editar
    await context.bot.send_message(
        chat_id=update.message.from_user.id,
        text='Escolha uma oferta abaixo:',
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def confirmar_plano(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    plano_index = int(query.data.split('_')[-1])
    planos = manager.get_bot_plans(context.bot_data['id'])
    
    if len(planos) > plano_index:
        plano = planos[plano_index]
        
        # Salva o índice do plano selecionado no contexto
        context.user_data['plano_selecionado'] = plano_index
        
        # Verifica se este plano tem order bump
        orderbump = manager.get_orderbump_by_plan(context.bot_data['id'], plano_index)
        
        if orderbump:
            # Se tem order bump, mostra a oferta primeiro
            payment_id = manager.create_payment(str(query.from_user.id), plano, plano['name'], context.bot_data['id'])
            
            keyboard = [
                [
                    InlineKeyboardButton('✅ 𝗔𝗰𝗲𝗶𝘁𝗮𝗿', callback_data=f'orderbump_aceitar_{payment_id}'),
                    InlineKeyboardButton('❌ Perder Oferta', callback_data=f'orderbump_recusar_{payment_id}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Envia a mensagem do order bump
            if orderbump.get('media') and orderbump['media']:
                if orderbump.get('text'):
                    if orderbump['media']['type'] == 'photo':
                        await query.message.reply_photo(
                            photo=orderbump['media']['file'],
                            caption=orderbump['text'],
                            reply_markup=reply_markup
                        )
                    else:
                        await query.message.reply_video(
                            video=orderbump['media']['file'],
                            caption=orderbump['text'],
                            reply_markup=reply_markup
                        )
                else:
                    if orderbump['media']['type'] == 'photo':
                        await query.message.reply_photo(
                            photo=orderbump['media']['file'],
                            reply_markup=reply_markup
                        )
                    else:
                        await query.message.reply_video(
                            video=orderbump['media']['file'],
                            reply_markup=reply_markup
                        )
            else:
                await query.message.reply_text(
                    orderbump.get('text', 'Oferta especial disponível!'),
                    reply_markup=reply_markup
                )
        else:
            # Se não tem order bump, segue o fluxo normal
            payment_id = manager.create_payment(str(query.from_user.id), plano, plano['name'], context.bot_data['id'])
            keyboard = [
                [InlineKeyboardButton('💠 Pagar via PIX 💠', callback_data=f'pagar_{payment_id}')]
            ]
            names = {
                'dia':'dias',
                'semana':'semanas',
                'mes':'meses',
                'ano':'anos',
                'eterno':''
            }
        
            reply_markup = InlineKeyboardMarkup(keyboard)
            valor = plano['value']
        
            if plano['time'] == 1:
                names = {
                'dia':'dia',
                'semana':'semana',
                'mes':'mes',
                'ano':'ano',
                'eterno':''
            }
        
            if plano['time_type'] != 'eterno':
                await query.message.reply_text(f"Plano selecionado com sucesso\.\n• Título\: {escape_markdown_v2(plano['name'])}\n• Duração\: {plano['time']} {names[plano['time_type']]}\n• Valor\: R\$ {escape_markdown_v2(str(valor))}", reply_markup=reply_markup, parse_mode='MarkdownV2')
            else:
                await query.message.reply_text(f"Plano selecionado com sucesso\.\n• Título\: {escape_markdown_v2(plano['name'])}\n• Duração\: Vitalicio\n• Valor\: R\$ {escape_markdown_v2(str(valor))}", reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await query.message.reply_text(f'⛔ Erro ao encontrar oferta')

async def exibir_plano(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    payment_index = query.data.split('_')[-1]
    plano = json.loads(manager.get_payment_plan_by_id(payment_index))

    keyboard = [
        [InlineKeyboardButton('💠 Pagar via PIX 💠', callback_data=f'pagar_{payment_index}')]
    ]
    names = {
        'dia':'dias',
        'semana':'semanas',
        'mes':'meses',
        'ano':'anos',
        'eterno':''
    }
    reply_markup = InlineKeyboardMarkup(keyboard)
    valor = plano['value']
    if plano['time'] == 1:
            names = {
            'dia':'dia',
            'semana':'semana',
            'mes':'mes',
            'ano':'ano',
            'eterno':''
        }
    if plano['time_type'] != 'eterno':
        await query.message.reply_text(f"Plano selecionado com sucesso\.\n• Título\: {escape_markdown_v2(plano['name'])}\n• Duração\: {plano['time']} {names[plano['time_type']]}\n• Valor\: R\$ {escape_markdown_v2(str(valor))}", reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await query.message.reply_text(f"Plano selecionado com sucesso\.\n• Título\: {escape_markdown_v2(plano['name'])}\n• Duração\: Vitalicio\n• Valor\: R\$ {escape_markdown_v2(str(valor))}", reply_markup=reply_markup, parse_mode='MarkdownV2')

async def notificar_admin(chat_id, plano_escolhido, bot_application, admin):
    bot_instance = bot_application.bot
    try:
        user = await bot_instance.get_chat(int(chat_id))
        username = user.username or "Não definido"
        first_name = user.first_name or "Não definido"
        mensagem_venda = (
            f"✅ Venda realizada!\n\n"
            f"🆔 Clientid: {chat_id}\n"
            f"👤 User: @{username}\n"
            f"📝 Nome: {first_name}\n"
            f"💵 Valor: R$ {str(plano_escolhido['value']).replace('.', ',')}\n"
            f"🔗 Plano: {plano_escolhido['name']}"
        )
        
        # Personaliza o nome do plano para upsell/downsell/recovery
        if plano_escolhido.get('is_upsell'):
            plano_escolhido['name'] = f"UPSELL - {plano_escolhido['name']}"
        elif plano_escolhido.get('is_downsell'):
            plano_escolhido['name'] = f"DOWNSELL - {plano_escolhido['name']}"
        elif plano_escolhido.get('has_orderbump'):
            plano_escolhido['name'] = f"COM ORDERBUMP - {plano_escolhido['name']}"
        elif plano_escolhido.get('is_recovery'):
            plano_escolhido['name'] = f"RECUPERAÇÃO - {plano_escolhido.get('recovery_name', 'Sem nome')} - {plano_escolhido['name']} ({plano_escolhido.get('discount', 0)}% OFF)"
        
        await bot_instance.send_message(chat_id=int(admin), text=mensagem_venda)
    except Exception as e:
        print(f'[ERROR] Erro ao notificar admin? {e}')