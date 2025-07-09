import asyncio
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import modules.manager as manager

async def send_recovery(context, user_id, recovery_data, bot_id):
    """Envia uma recuperação específica para o usuário"""
    try:
        # Pega os planos do bot
        planos = manager.get_bot_plans(bot_id)
        if not planos:
            return False
        
        # Calcula o desconto
        desconto = recovery_data['discount']
        
        # Monta os botões dos planos com desconto
        keyboard_plans = []
        for plan_index in range(len(planos)):
            plano = planos[plan_index]
            valor_original = plano['value']
            valor_com_desconto = round(valor_original * (1 - desconto / 100), 2)
            
            # Formata o botão
            if desconto > 0:
                botao_texto = f"{plano['name']} por R${valor_com_desconto:.2f} ({int(desconto)}% OFF)"
            else:
                botao_texto = f"{plano['name']} por R${valor_com_desconto:.2f}"
            
            # Cria um plano modificado para o pagamento
            plano_recovery = plano.copy()
            plano_recovery['value'] = valor_com_desconto
            plano_recovery['is_recovery'] = True
            plano_recovery['recovery_name'] = recovery_data['name']
            plano_recovery['original_value'] = valor_original
            plano_recovery['discount'] = desconto
            
            # Cria o pagamento com o plano modificado
            payment_id = manager.create_payment(user_id, plano_recovery, f"{plano['name']} - Recovery", bot_id)
            
            # Gera PIX direto
            keyboard_plans.append([InlineKeyboardButton(botao_texto, callback_data=f"pagar_{payment_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard_plans)
        
        # Envia a mensagem da recuperação
        if recovery_data['media']:
            if recovery_data['text']:
                if recovery_data['media']['type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=recovery_data['media']['file'],
                        caption=recovery_data['text'],
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=recovery_data['media']['file'],
                        caption=recovery_data['text'],
                        reply_markup=reply_markup
                    )
            else:
                if recovery_data['media']['type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=recovery_data['media']['file'],
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=recovery_data['media']['file'],
                        reply_markup=reply_markup
                    )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=recovery_data.get('text', 'Oferta especial para você!'),
                reply_markup=reply_markup
            )
        
        return True
        
    except Exception as e:
        print(f"Erro ao enviar recuperação: {e}")
        return False

async def process_recovery_sequence(context, user_id, bot_id):
    """Processa a sequência de recuperações para um usuário"""
    try:
        # Pega todas as recuperações do bot
        recoveries = manager.get_all_recovery_messages(bot_id)
        if not recoveries:
            print(f"Nenhuma recuperação configurada para bot {bot_id}")
            return
        
        print(f"Iniciando {len(recoveries)} recuperações para usuário {user_id}")
        
        # Processa cada recuperação
        for recovery in recoveries:
            # Aguarda o tempo configurado (delay está em minutos)
            delay_seconds = recovery['delay'] * 60
            print(f"Aguardando {recovery['delay']} minutos para recuperação '{recovery['name']}'")
            await asyncio.sleep(delay_seconds)
            
            # Verifica se o usuário ainda está sendo rastreado (não comprou)
            tracking = manager.get_recovery_tracking(user_id, bot_id)
            if not tracking or tracking[4] != 'active':
                print(f"Recuperação cancelada para usuário {user_id} - já comprou ou foi cancelado")
                return
            
            # Envia a recuperação
            success = await send_recovery(context, user_id, recovery, bot_id)
            
            if success:
                print(f"Recuperação '{recovery['name']}' enviada para usuário {user_id}")
            else:
                print(f"Erro ao enviar recuperação '{recovery['name']}' para usuário {user_id}")
        
        # Após enviar todas as recuperações, para o tracking
        manager.stop_recovery_tracking(user_id, bot_id)
        print(f"Ciclo de recuperação completo para usuário {user_id}")
            
    except Exception as e:
        print(f"Erro no processo de recuperação: {e}")
        # Em caso de erro, para o tracking
        manager.stop_recovery_tracking(user_id, bot_id)

def start_recovery_for_user(context, user_id, bot_id):
    """Inicia o processo de recuperação para um usuário"""
    # Cria a tabela se não existir
    manager.create_recovery_tracking_table()
    
    # Verifica se já existe um rastreamento ativo
    existing_tracking = manager.get_recovery_tracking(user_id, bot_id)
    
    if existing_tracking:
        print(f"Usuário {user_id} já tem recuperação ativa - ignorando novo /start")
        return
    
    # Verifica se há recuperações configuradas
    recoveries = manager.get_all_recovery_messages(bot_id)
    if not recoveries:
        print(f"Nenhuma recuperação configurada para bot {bot_id}")
        return
    
    # Inicia o rastreamento
    manager.start_recovery_tracking(user_id, bot_id)
    
    # Cria uma task assíncrona para processar as recuperações
    asyncio.create_task(process_recovery_sequence(context, user_id, bot_id))
    print(f"Sistema de recuperação iniciado para usuário {user_id}")