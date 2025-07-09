import modules.manager as manager
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from modules.utils import process_command, is_admin, cancel, error_callback, escape_markdown_v2

# Estados da conversa
RECUPERACAO_MENU, RECUPERACAO_NOME, RECUPERACAO_MENSAGEM, RECUPERACAO_PORCENTAGEM, RECUPERACAO_TEMPO_TIPO, RECUPERACAO_TEMPO, RECUPERACAO_CONFIRMAR, RECUPERACAO_VER, RECUPERACAO_DELETAR = range(9)

keyboardc = [
    [InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]
]
cancel_markup = InlineKeyboardMarkup(keyboardc)

async def recuperacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_check = await process_command(update, context)
    if not command_check:
        return ConversationHandler.END
    
    if not await is_admin(context, update.message.from_user.id):
        return ConversationHandler.END
    
    context.user_data['conv_state'] = "recuperacao"
    
    # Conta quantas recuperações existem
    count = manager.count_recovery_messages(context.bot_data['id'])
    
    keyboard = []
    
    if count > 0:
        keyboard.append([InlineKeyboardButton(f"👁️ VER RECUPERAÇÕES ({count})", callback_data="ver_recuperacoes")])
        keyboard.append([InlineKeyboardButton("➕ CRIAR RECUPERAÇÃO", callback_data="criar_recuperacao")])
        keyboard.append([InlineKeyboardButton("➖ REMOVER", callback_data="remover_recuperacao")])
    else:
        keyboard.append([InlineKeyboardButton("➕ CRIAR RECUPERAÇÃO", callback_data="criar_recuperacao")])
    
    keyboard.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if count == 0:
        texto = "🔄 SISTEMA DE RECUPERAÇÃO\n\nVocê ainda não tem recuperações configuradas."
    else:
        texto = f"🔄 SISTEMA DE RECUPERAÇÃO\n\nVocê tem {count} recuperações ativas."
    
    await update.message.reply_text(texto, reply_markup=reply_markup)
    return RECUPERACAO_MENU

async def recuperacao_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    
    elif query.data == 'criar_recuperacao':
        # Inicia criação de nova recuperação
        context.user_data['recovery_context'] = {
            'name': None,
            'media': None,
            'text': None,
            'discount': None,
            'delay': None
        }
        
        await query.message.edit_text(
            "🔄 NOVA RECUPERAÇÃO\n\n"
            "📝 Digite um nome para esta recuperação:\n"
            "(Ex: 'Oferta 24h', 'Desconto Relâmpago', etc)",
            reply_markup=cancel_markup
        )
        return RECUPERACAO_NOME
    
    elif query.data == 'ver_recuperacoes':
        # Mostra todas as recuperações
        recoveries = manager.get_all_recovery_messages(context.bot_data['id'])
        
        if not recoveries:
            texto = "❌ Nenhuma recuperação encontrada."
        else:
            texto = "👁️ SUAS RECUPERAÇÕES\n\n"
            for i, rec in enumerate(recoveries, 1):
                tempo_str = f"{rec['delay']}min" if rec['delay'] < 60 else f"{rec['delay']//60}h"
                if rec['delay'] >= 1440:
                    tempo_str = f"{rec['delay']//1440}d"
                
                texto += f"{i}️⃣ '{rec['name']}' - {rec['discount']}% em {tempo_str}\n"
            
            texto += f"\nTotal: {len(recoveries)} recuperações ativas\n"
            texto += "Ordem: Por tempo (mais cedo primeiro)"
        
        keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="voltar_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(texto, reply_markup=reply_markup)
        return RECUPERACAO_VER
    
    elif query.data == 'remover_recuperacao':
        # Lista recuperações para remover
        recoveries = manager.get_all_recovery_messages(context.bot_data['id'])
        
        if not recoveries:
            await query.message.edit_text("❌ Nenhuma recuperação para remover.")
            return ConversationHandler.END
        
        keyboard = []
        for rec in recoveries:
            tempo_str = f"{rec['delay']}min" if rec['delay'] < 60 else f"{rec['delay']//60}h"
            if rec['delay'] >= 1440:
                tempo_str = f"{rec['delay']//1440}d"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ '{rec['name']}' - {rec['discount']}% em {tempo_str}",
                    callback_data=f"del_{rec['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            "➖ REMOVER RECUPERAÇÃO\n\n"
            "Selecione qual deseja remover:",
            reply_markup=reply_markup
        )
        return RECUPERACAO_DELETAR

async def recuperacao_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("⛔ Por favor, envie um nome válido:", reply_markup=cancel_markup)
        return RECUPERACAO_NOME
    
    context.user_data['recovery_context']['name'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"🔄 NOVA RECUPERAÇÃO - '{context.user_data['recovery_context']['name']}'\n\n"
        "📤 Envie a mensagem (mídia + texto) desta recuperação:",
        reply_markup=cancel_markup
    )
    return RECUPERACAO_MENSAGEM

async def recuperacao_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        save = {
            'media': None,
            'text': None
        }
        
        # Verifica se tem mídia
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            save['media'] = {
                'file': photo_file.file_id,
                'type': 'photo'
            }
        elif update.message.video:
            video_file = await update.message.video.get_file()
            save['media'] = {
                'file': video_file.file_id,
                'type': 'video'
            }
        elif update.message.text:
            save['text'] = update.message.text
        else:
            await update.message.reply_text("⛔ Somente texto ou mídia são permitidos:", reply_markup=cancel_markup)
            return RECUPERACAO_MENSAGEM
        
        # Captura caption se houver
        if update.message.caption:
            save['text'] = update.message.caption
        
        # Salva no contexto
        context.user_data['recovery_context']['media'] = save['media']
        context.user_data['recovery_context']['text'] = save['text']
        
        nome = context.user_data['recovery_context']['name']
        await update.message.reply_text(
            f"🔄 NOVA RECUPERAÇÃO - '{nome}'\n\n"
            "💸 Qual o desconto (%) para esta recuperação?\n"
            "Digite apenas o número (ex: 10 para 10%)",
            reply_markup=cancel_markup
        )
        return RECUPERACAO_PORCENTAGEM
        
    except Exception as e:
        await update.message.reply_text(f"⛔ Erro ao salvar mensagem: {str(e)}")
        context.user_data['conv_state'] = False
        return ConversationHandler.END

async def recuperacao_porcentagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("⛔ Por favor, envie apenas o número:", reply_markup=cancel_markup)
        return RECUPERACAO_PORCENTAGEM
    
    try:
        porcentagem = float(update.message.text.replace(',', '.'))
        if porcentagem < 0 or porcentagem >= 100:
            await update.message.reply_text("⛔ A porcentagem deve estar entre 0 e 99:", reply_markup=cancel_markup)
            return RECUPERACAO_PORCENTAGEM
        
        context.user_data['recovery_context']['discount'] = porcentagem
        
        nome = context.user_data['recovery_context']['name']
        
        # Monta teclado para escolher unidade de tempo
        keyboard = [
            [InlineKeyboardButton("⏱️ Minutos", callback_data="tempo_minutos")],
            [InlineKeyboardButton("🕐 Horas", callback_data="tempo_horas")],
            [InlineKeyboardButton("📅 Dias", callback_data="tempo_dias")],
            [InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔄 NOVA RECUPERAÇÃO - '{nome}'\n\n"
            "⏰ Quando enviar após o /start?",
            reply_markup=reply_markup
        )
        return RECUPERACAO_TEMPO_TIPO
        
    except ValueError:
        await update.message.reply_text("⛔ Envie um número válido:", reply_markup=cancel_markup)
        return RECUPERACAO_PORCENTAGEM

async def recuperacao_tempo_tipo(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    
    unidade = query.data.split('_')[1]
    context.user_data['recovery_context']['tempo_unidade'] = unidade
    
    nome = context.user_data['recovery_context']['name']
    
    await query.message.edit_text(
        f"🔄 NOVA RECUPERAÇÃO - '{nome}'\n\n"
        f"⏰ Quantos {unidade} após o /start?\n"
        "(Digite apenas o número)",
        reply_markup=cancel_markup
    )
    return RECUPERACAO_TEMPO

async def recuperacao_tempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("⛔ Por favor, envie apenas o número:", reply_markup=cancel_markup)
        return RECUPERACAO_TEMPO
    
    try:
        tempo = int(update.message.text)
        if tempo <= 0:
            await update.message.reply_text("⛔ O tempo deve ser maior que zero:", reply_markup=cancel_markup)
            return RECUPERACAO_TEMPO
        
        # Converte para minutos
        unidade = context.user_data['recovery_context']['tempo_unidade']
        if unidade == 'minutos':
            delay_minutos = tempo
        elif unidade == 'horas':
            delay_minutos = tempo * 60
        elif unidade == 'dias':
            delay_minutos = tempo * 24 * 60
        
        context.user_data['recovery_context']['delay'] = delay_minutos
        
        # Monta mensagem de confirmação
        rec = context.user_data['recovery_context']
        keyboard = [
            [InlineKeyboardButton("✅ CRIAR", callback_data="confirmar")],
            [InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        tempo_str = f"{tempo} {unidade}"
        
        await update.message.reply_text(
            f"📋 CONFIRMAR RECUPERAÇÃO\n\n"
            f"Nome: {rec['name']}\n"
            f"Desconto: {rec['discount']}%\n"
            f"Tempo: {tempo_str} após /start\n"
            f"Mensagem: ✅ Configurada\n\n"
            f"Deseja criar esta recuperação?",
            reply_markup=reply_markup
        )
        return RECUPERACAO_CONFIRMAR
        
    except ValueError:
        await update.message.reply_text("⛔ Envie um número válido:", reply_markup=cancel_markup)
        return RECUPERACAO_TEMPO

async def recuperacao_confirmar(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    
    elif query.data == 'confirmar':
        try:
            # Salva a recuperação
            rec = context.user_data['recovery_context']
            bot_id = context.bot_data['id']
            
            recovery_id = manager.create_recovery_message(
                bot_id=bot_id,
                name=rec['name'],
                media=rec['media'],
                text=rec['text'],
                discount=rec['discount'],
                delay=rec['delay']
            )
            
            await query.message.edit_text(f"✅ Recuperação '{rec['name']}' criada com sucesso!")
            
        except Exception as e:
            await query.message.edit_text(f"⛔ Erro ao criar recuperação: {str(e)}")
        
        context.user_data['conv_state'] = False
        return ConversationHandler.END

async def recuperacao_ver(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'voltar_menu':
        # Volta para o menu principal
        count = manager.count_recovery_messages(context.bot_data['id'])
        
        keyboard = []
        if count > 0:
            keyboard.append([InlineKeyboardButton(f"👁️ VER RECUPERAÇÕES ({count})", callback_data="ver_recuperacoes")])
            keyboard.append([InlineKeyboardButton("➕ CRIAR RECUPERAÇÃO", callback_data="criar_recuperacao")])
            keyboard.append([InlineKeyboardButton("➖ REMOVER", callback_data="remover_recuperacao")])
        else:
            keyboard.append([InlineKeyboardButton("➕ CRIAR RECUPERAÇÃO", callback_data="criar_recuperacao")])
        
        keyboard.append([InlineKeyboardButton("❌ CANCELAR", callback_data="cancelar")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if count == 0:
            texto = "🔄 SISTEMA DE RECUPERAÇÃO\n\nVocê ainda não tem recuperações configuradas."
        else:
            texto = f"🔄 SISTEMA DE RECUPERAÇÃO\n\nVocê tem {count} recuperações ativas."
        
        await query.message.edit_text(texto, reply_markup=reply_markup)
        return RECUPERACAO_MENU

async def recuperacao_deletar(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancelar':
        await cancel(update, context)
        return ConversationHandler.END
    
    try:
        recovery_id = int(query.data.split('_')[1])
        manager.delete_recovery_message(recovery_id)
        
        await query.message.edit_text("✅ Recuperação removida com sucesso!")
        
    except Exception as e:
        await query.message.edit_text(f"⛔ Erro ao remover recuperação: {str(e)}")
    
    context.user_data['conv_state'] = False
    return ConversationHandler.END

# ConversationHandler
conv_handler_recuperacao = ConversationHandler(
    entry_points=[CommandHandler("recuperacao", recuperacao)],
    states={
        RECUPERACAO_MENU: [CallbackQueryHandler(recuperacao_menu)],
        RECUPERACAO_NOME: [MessageHandler(~filters.COMMAND, recuperacao_nome), CallbackQueryHandler(cancel)],
        RECUPERACAO_MENSAGEM: [MessageHandler(~filters.COMMAND, recuperacao_mensagem), CallbackQueryHandler(cancel)],
        RECUPERACAO_PORCENTAGEM: [MessageHandler(~filters.COMMAND, recuperacao_porcentagem), CallbackQueryHandler(cancel)],
        RECUPERACAO_TEMPO_TIPO: [CallbackQueryHandler(recuperacao_tempo_tipo)],
        RECUPERACAO_TEMPO: [MessageHandler(~filters.COMMAND, recuperacao_tempo), CallbackQueryHandler(cancel)],
        RECUPERACAO_CONFIRMAR: [CallbackQueryHandler(recuperacao_confirmar)],
        RECUPERACAO_VER: [CallbackQueryHandler(recuperacao_ver)],
        RECUPERACAO_DELETAR: [CallbackQueryHandler(recuperacao_deletar)]
    },
    fallbacks=[CallbackQueryHandler(error_callback)]
)