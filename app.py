from flask import Flask, jsonify, request, send_file, session, redirect, url_for
import modules.manager as manager
import asyncio, json, requests, datetime, time
import mercadopago, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from multiprocessing import Process
from bot import run_bot_sync

# Configurações do Mercado Pago
CLIENT_ID = os.environ.get("CLIENT_ID", "4714763730515747")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "i33hQ8VZ11pYH1I3xMEMECphRJjT0CiP")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", 'kekel')

# Carrega configurações
try:
    config = json.loads(open('./config.json', 'r').read())
except:
    config = {}

# Usa variáveis de ambiente com fallback para config.json
IP_DA_VPS = os.environ.get("URL", config.get("url", "https://localhost:4040"))
REGISTRO_TOKEN = os.environ.get("REGISTRO_TOKEN", config.get("registro", ""))
ADMIN_PASSWORD = os.environ.get("PASSWORD", config.get("password", "adminadmin"))

# Porta do Railway ou padrão
port = int(os.environ.get("PORT", 4040))

dashboard_data = {
    "botsActive": 0,
    "usersCount": 0,
    "salesCount": 0
}

bots_data = {}
processes = {}
tokens = []
event_loop = asyncio.new_event_loop()
# Estados para o bot de registro
REGISTRO_MENU, REGISTRO_AGUARDANDO_TOKEN, REGISTRO_SELECIONAR_BOT, REGISTRO_AGUARDANDO_NOVO_TOKEN = range(4)

def initialize_all_registered_bots():
    """Inicializa todos os bots registrados e ativos com carregamento gradual."""
    print('Inicializando bots registrados...')
    
    # Marca todos os bots como ativos para não deletar bots existentes
    manager.mark_all_bots_active()
    
    global bots_data, processes
    bots = manager.get_all_bots()
    total_bots = len(bots)
    print(f'Encontrados {total_bots} bots')
    
    # Define tamanho do lote e delay
    BATCH_SIZE = 10
    BATCH_DELAY = 5  # segundos entre lotes
    
    # Processa bots em lotes
    for i in range(0, total_bots, BATCH_SIZE):
        batch = bots[i:i + BATCH_SIZE]
        batch_number = (i // BATCH_SIZE) + 1
        total_batches = (total_bots + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f'\n📦 Iniciando lote {batch_number}/{total_batches} ({len(batch)} bots)...')
        
        for bot in batch:
            bot_id = bot[0]

            # Verifica se já existe um processo rodando para este bot
            if str(bot_id) in processes and processes[str(bot_id)].is_alive():
                print(f"Bot {bot_id} já está em execução. Ignorando nova inicialização.")
                continue

            try:
                start_bot(bot[1], bot_id)
                print(f"✅ Bot {bot_id} iniciado com sucesso.")
                
                # CORREÇÃO: Garante que o bot_id seja string no dicionário processes
                if str(bot_id) not in processes and bot_id in processes:
                    processes[str(bot_id)] = processes[bot_id]
                    processes.pop(bot_id)
                
            except Exception as e:
                print(f"❌ Erro ao iniciar o bot {bot_id}: {e}")
        
        # Aguarda antes do próximo lote (exceto no último)
        if i + BATCH_SIZE < total_bots:
            print(f'⏳ Aguardando {BATCH_DELAY} segundos antes do próximo lote...')
            time.sleep(BATCH_DELAY)
    
    # Aguarda um pouco para garantir que todos os bots iniciaram
    print('\n✅ Todos os bots foram iniciados!')
    time.sleep(2)
    
    # Inicia disparos programados para todos os bots
    print('\nInicializando disparos programados...')
    bots_with_broadcasts = manager.get_all_bots_with_scheduled_broadcasts()
    print(f'Encontrados {len(bots_with_broadcasts)} bots com disparos programados')
    
    # Os disparos serão iniciados individualmente por cada bot quando ele iniciar

@app.route('/callback', methods=['GET'])
def callback():
    """
    Endpoint para receber o webhook de redirecionamento do Mercado Pago.
    """
    TOKEN_URL = "https://api.mercadopago.com/oauth/token"

    authorization_code = request.args.get('code')
    bot_id = request.args.get('state')

    if not authorization_code:
        return jsonify({"error": "Authorization code not provided"}), 400

    try:
        payload = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": authorization_code,
            "redirect_uri": IP_DA_VPS+'/callback',
            "state":bot_id,
        }
        
        response = requests.post(TOKEN_URL, data=payload)
        response_data = response.json()

        if response.status_code == 200:
            access_token = response_data.get("access_token")
            print(f"Token MP recebido para bot {bot_id}")
            manager.update_bot_gateway(bot_id, {'type':"MP", 'token':access_token})
            return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Cadastrado</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #333;
        }
        .container {
            background-color: #fff;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 20px 30px;
            text-align: center;
            max-width: 400px;
        }
        .container h1 {
            color: #4caf50;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .container p {
            font-size: 16px;
            margin-bottom: 20px;
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            font-size: 14px;
            color: #fff;
            background-color: #4caf50;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s ease;
        }
        .btn:hover {
            background-color: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Token Cadastrado com Sucesso!</h1>
        <p>O seu token Mercado Pago está pronto para uso.</p>
    </div>
</body>
</html>
"""
        else:
            return jsonify({"error": response_data}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/mp', methods=['POST'])
def handle_webhook():
    data = request.get_json(silent=True)
    print(f"Webhook MP recebido: {data}")
    
    if data and data.get('type') == 'payment':
        transaction_id = (data.get('data').get('id'))
        print(f'Pagamento {transaction_id} recebido - Mercado Pago')
        payment = manager.get_payment_by_trans_id(transaction_id)
        
        if payment:
            print(payment)
            bot_id = json.loads(payment[4])
            token = manager.get_bot_gateway(bot_id)
            sdk = mercadopago.SDK(token['token'])
            pagamento = sdk.payment().get(transaction_id)
            pagamento_status = pagamento["response"]["status"]

            if pagamento_status == "approved":
                print(f'Pagamento {transaction_id} aprovado - Mercado Pago')
                manager.update_payment_status(transaction_id, 'paid')
                return jsonify({"message": "Webhook recebido com sucesso."}), 200
    
    return jsonify({"message": "Evento ignorado."}), 400

@app.route('/webhook/pp', methods=['POST'])
def webhook():
    if request.content_type == 'application/json':
        data = request.get_json()
    elif request.content_type == 'application/x-www-form-urlencoded':
        data = request.form.to_dict()
    else:
        print("[ERRO] Tipo de conteúdo não suportado")
        return jsonify({"error": "Unsupported Media Type"}), 415

    if not data:
        print("[ERRO] Dados JSON ou Form Data inválidos")
        return jsonify({"error": "Invalid JSON or Form Data"}), 400
    
    print(f"[DEBUG] Webhook PP recebido: {data}")
    transaction_id = data.get("id", "").lower()
    
    if data.get('status', '').lower() == 'paid':
        print(f'Pagamento {transaction_id} pago - PushinPay')
        manager.update_payment_status(transaction_id, 'paid')
    else:
        print(f"[ERRO] Status do pagamento não é 'paid': {data.get('status')}")

    return jsonify({"status": "success"})

@app.route('/', methods=['GET'])
def home():
    if session.get("auth", False):
        dashboard_data['botsActive'] = manager.count_bots()
        dashboard_data['usersCount'] = '?'
        dashboard_data['salesCount'] = len(manager.get_all_payments_by_status('finished'))
        return send_file('./templates/terminal.html')
    return redirect(url_for('login'))

@app.route('/visualizar', methods=['GET'])
def view():
    if session.get("auth", False):
        return send_file('./templates/bots.html')
    return redirect(url_for('login'))

@app.route('/delete/<id>', methods=['DELETE'])
async def delete(id):
    if session.get("auth", False):
        # Remove apenas o processo e dados em memória
        if id in processes.keys():
            processes.pop(id)
        if id in bots_data:
            bots_data.pop(id)
        
        # Remove completamente do banco
        manager.delete_bot(id)
        return 'true'
    else:
        return 'Unauthorized', 403

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['auth'] = True
            return redirect('/')
    return '''
        <form method="post">
            <p><input type="text" name="password" placeholder="Digite a senha"></p>
            <p><input type="submit" value="Entrar"></p>
        </form>
    '''

def start_bot(new_token, bot_id):
    """Inicia um novo bot em um processo separado."""
    bot_id = str(bot_id)
    
    # NOVA VERIFICAÇÃO: Procura por processos com o mesmo token
    global processes, bots_data
    
    # Verifica se já existe um processo com este token
    for pid, process in list(processes.items()):
        if pid in bots_data and bots_data[pid].get('token') == new_token:
            print(f"Token {new_token[:20]}... já está em uso pelo bot {pid}")
            
            # Para o processo antigo
            try:
                if process and process.is_alive():
                    print(f"Parando processo antigo do bot {pid}")
                    process.terminate()
                    time.sleep(0.5)
                    if process.is_alive():
                        process.kill()
                    process.join(timeout=2)
            except Exception as e:
                print(f"Erro ao parar processo antigo: {e}")
            
            # Remove dos dicionários
            processes.pop(pid, None)
            bots_data.pop(pid, None)
    
    # Verifica se o bot_id já tem processo
    if bot_id in processes:
        process = processes[bot_id]
        if process and process.is_alive():
            print(f"Bot {bot_id} já tem processo ativo. Parando...")
            try:
                process.terminate()
                time.sleep(0.5)
                if process.is_alive():
                    process.kill()
                process.join(timeout=2)
            except:
                pass
        processes.pop(bot_id, None)
    
    # Agora inicia o novo processo
    process = Process(target=run_bot_sync, args=(new_token, bot_id))
    process.start()
    tokens.append(new_token)
    
    bot = manager.get_bot_by_id(bot_id)
    bot_details = manager.check_bot_token(new_token)
    bot_obj = {
        'id': bot_id,
        'url':f'https://t.me/{bot_details["result"].get("username", "INDEFINIDO")}' if bot_details else 'Token Inválido',
        'token': new_token,  # IMPORTANTE: Salvar o token aqui
        'owner': bot[2],
        'data': json.loads(bot[4])
    }
    bots_data[bot_id] = bot_obj
    processes[bot_id] = process
    print(f"Bot {bot_id} processo iniciado - PID: {process.pid}")
    return True
def check_and_remove_inactive_bots():
    """Remove bots inativos do sistema"""
    global processes, bots_data
    
    try:
        # Pega bots inativos há mais de 5 minutos (para teste)
        inactive_bots = manager.get_inactive_bots(minutes=21600)
        
        for bot_data in inactive_bots:
            bot_id = str(bot_data[0])
            bot_token = bot_data[1]
            owner_id = bot_data[2]
            
            print(f"Removendo bot inativo {bot_id} do sistema")
            
            # Para o processo se estiver rodando
            if bot_id in processes:
                try:
                    process = processes[bot_id]
                    if process and process.is_alive():
                        process.terminate()
                        time.sleep(0.5)
                        if process.is_alive():
                            process.kill()
                        process.join(timeout=2)
                    processes.pop(bot_id)
                except Exception as e:
                    print(f"Erro ao parar processo: {e}")
            
            # Remove dos dados em memória
            if bot_id in bots_data:
                bots_data.pop(bot_id)
                
    except Exception as e:
        print(f"Erro ao verificar bots inativos: {e}")
        
def inactivity_checker_thread():
    """Thread para verificar bots inativos periodicamente"""
    while True:
        time.sleep(18000)  # Verifica a cada 5 horas
        check_and_remove_inactive_bots()

async def receive_token_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verifica se é callback de cancelar
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == "registro_cancelar_silencioso":
            # Volta para o menu principal sem mensagem
            return await mostrar_menu_principal(query.message, query.from_user)
    
    # Processa o token enviado
    if update.message and update.message.text:
        new_token = update.message.text.strip()
        admin_id = update.effective_user.id
        
        # Verifica se já existe
        if manager.bot_exists(new_token):
            await update.message.reply_text(
                '⚠️ <b>Token já registrado!</b>\n\n'
                'Este bot já está cadastrado no sistema.',
                parse_mode='HTML'
            )
            return ConversationHandler.END
            
        # Verifica se o token é válido
        telegram_bot = manager.check_bot_token(new_token)
        if telegram_bot and telegram_bot.get('result'):
            bot_info = telegram_bot['result']
            bot_id = bot_info.get('id')
            bot_username = bot_info.get('username', 'sem_username')
            bot_name = bot_info.get('first_name', 'Sem nome')
            
            if bot_id:
                # Cria o bot no banco
                manager.create_bot(str(bot_id), new_token, admin_id)
                
                # Inicia o bot
                start_bot(new_token, bot_id)
                
                await update.message.reply_text(
                    f'✅ <b>Bot cadastrado com sucesso!</b>\n\n'
                    f'<b>Nome:</b> {bot_name}\n'
                    f'<b>Username:</b> @{bot_username}\n'
                    f'<b>ID:</b> {bot_id}\n\n'
                    f'🔗 Link: t.me/{bot_username}\n\n'
                    f'✨ Seu bot já está online e funcionando!',
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    '❌ <b>Erro ao obter ID do bot!</b>\n\n'
                    'Tente novamente mais tarde.',
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(
                '❌ <b>Token inválido!</b>\n\n'
                'Verifique se o token está correto e tente novamente.\n\n'
                '💡 <i>Dica: O token deve ter o formato:</i>\n'
                '<code>123456789:ABCdefGHIjklMNOpqrsTUVwxyz</code>',
                parse_mode='HTML'
            )
    
    return ConversationHandler.END

async def start_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Texto de apresentação
    welcome_text = (
        f"<b>Bem-vindo</b> {user_name} 🥂\n\n"
        f"🥷 Hora de colocar a caixa pra movimentar com o melhor <b>Bot de Pagamento do Telegram!</b>\n\n"
        "⚙️ <b>Sistema completo,</b> desde funcionalidades para uma maior conversão a taxas justas.\n\n"
        "O que você deseja fazer?"
    )
    
    # Botões do menu
    keyboard = [
        [InlineKeyboardButton("📦 𝗖𝗮𝗱𝗮𝘀𝘁𝗿𝗮𝗿 𝗕𝗼𝘁", callback_data="registro_cadastrar")],
        [
            InlineKeyboardButton("👤 𝗠𝗲𝘂𝘀 𝗕𝗼𝘁𝘀", callback_data="registro_ver_bots"),
            InlineKeyboardButton("♻️ 𝗧𝗿𝗼𝗰𝗮𝗿 𝗧𝗼𝗸𝗲𝗻", callback_data="registro_substituir")
        ],
        [
            InlineKeyboardButton("💰 𝗧𝗮𝘅𝗮𝘀", callback_data="registro_taxas"),
            InlineKeyboardButton("🙋‍♂ 𝗔𝗷𝘂𝗱𝗮", callback_data="registro_ajuda")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    return REGISTRO_MENU
    
    return REGISTRO_MENU

async def registro_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "registro_cadastrar":
        # Inicia processo de cadastro
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="registro_cancelar_silencioso")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🚀 <b>Como cadastrar na NGK Pay?</b> É simples! Basta seguir o tutorial:\n\n"
            "<b>1.</b> Crie um novo Bot no @Botfather\n"
            "<b>2.</b> Copie o Token do Bot\n"
            "<b>3.</b> Cole o Token aqui abaixo",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        return REGISTRO_AGUARDANDO_TOKEN
        
    elif query.data == "registro_ver_bots":
        # Mostra lista de bots do usuário
        user_id = query.from_user.id
        bots = manager.get_bots_by_owner(str(user_id))
        
        # Botão para voltar ao menu (definido antes para usar junto com o texto)
        keyboard = [[InlineKeyboardButton("🏠 Voltar", callback_data="registro_voltar_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not bots:
            await query.edit_message_text(
                "❌ <b>Nenhum bot cadastrado</b>\n\n"
                "Você ainda não possui bots cadastrados no sistema. "
                "Use o botão <b>Cadastrar Bot</b> para adicionar seu primeiro bot na NGK Pay.",
                parse_mode='HTML',
                reply_markup=reply_markup  # Adiciona o botão junto com o texto
            )
        else:
            bot_list = "🤖 <b>Seus Bots Cadastrados:</b>\n\n"
            for bot in bots:
                bot_id = bot[0]
                bot_token = bot[1]
                
                # Verifica se o bot está ativo
                bot_details = manager.check_bot_token(bot_token)
                if bot_details and bot_details.get('result'):
                    bot_username = bot_details['result'].get('username', 'INDEFINIDO')
                    bot_name = bot_details['result'].get('first_name', 'Sem nome')
                    bot_list += f"• <b>{bot_name}</b> - @{bot_username}\n"
                else:
                    bot_list += f"• Bot ID: {bot_id} (Token inválido)\n"
            
            bot_list += f"\n📊 <b>Total:</b> {len(bots)} bot(s)"
            
            await query.edit_message_text(
                bot_list, 
                parse_mode='HTML',
                reply_markup=reply_markup  # Adiciona o botão junto com o texto
            )
        
        return REGISTRO_MENU
        
    elif query.data == "registro_substituir":
        # Busca bots do usuário
        user_id = query.from_user.id
        bots = manager.get_bots_by_owner(str(user_id))
        
        if not bots:
            await query.edit_message_text(
                "📭 <b>Nenhum bot para substituir</b>\n\n"
                "Você precisa ter pelo menos um bot cadastrado para usar esta função.",
                parse_mode='HTML'
            )
            
            # Botão para voltar ao menu
            keyboard = [[InlineKeyboardButton("⬅️ VOLTAR", callback_data="registro_voltar_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup)
            return REGISTRO_MENU
        
        # Monta lista de bots para escolher
        await query.edit_message_text(
            "🔄 <b>Substituir Bot</b>\n\n"
            "Selecione o bot que deseja substituir:\n\n"
            "⚠️ <i>O bot selecionado será desativado e suas configurações "
            "serão transferidas para o novo bot.</i>",
            parse_mode='HTML'
        )
        
        keyboard = []
        for bot in bots:
            bot_id = bot[0]
            bot_token = bot[1]
            
            # Pega info do bot
            bot_details = manager.check_bot_token(bot_token)
            if bot_details and bot_details.get('result'):
                bot_username = bot_details['result'].get('username', 'INDEFINIDO')
                bot_name = bot_details['result'].get('first_name', 'Sem nome')
                button_text = f"{bot_name} (@{bot_username})"
            else:
                button_text = f"Bot ID: {bot_id} (Offline)"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"substituir_bot_{bot_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ CANCELAR", callback_data="registro_voltar_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_reply_markup(reply_markup)
        
        return REGISTRO_SELECIONAR_BOT
        
    elif query.data == "registro_voltar_menu":
        # Volta ao menu principal
        return await mostrar_menu_principal(query.message, query.from_user)

async def mostrar_menu_principal(message, user):
    """Função auxiliar para mostrar o menu principal"""
    user_name = user.first_name
    
    welcome_text = (
        f"<b>Bem-vindo</b> {user_name} 🥂\n\n"
        f"🥷 Hora de colocar a caixa pra movimentar com o melhor <b>Bot de Pagamento do Telegram!</b>\n\n"
        "⚙️ <b>Sistema completo,</b> desde funcionalidades para uma maior conversão a taxas justas.\n\n"
        "O que você deseja fazer?"
    )
    
    keyboard = [
        [InlineKeyboardButton("📦 𝗖𝗮𝗱𝗮𝘀𝘁𝗿𝗮𝗿 𝗕𝗼𝘁", callback_data="registro_cadastrar")],
        [
            InlineKeyboardButton("👤 𝗠𝗲𝘂𝘀 𝗕𝗼𝘁𝘀", callback_data="registro_ver_bots"),
            InlineKeyboardButton("♻️ 𝗧𝗿𝗼𝗰𝗮𝗿 𝗧𝗼𝗸𝗲𝗻", callback_data="registro_substituir")
        ],
        [
            InlineKeyboardButton("💰 𝗧𝗮𝘅𝗮𝘀", callback_data="registro_taxas"),
            InlineKeyboardButton("🙋‍♂ 𝗔𝗷𝘂𝗱𝗮", callback_data="registro_ajuda")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.edit_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    return REGISTRO_MENU

async def registro_selecionar_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "registro_voltar_menu":
        return await mostrar_menu_principal(query.message, query.from_user)
    
    if query.data.startswith("substituir_bot_"):
        # Extrai o ID do bot selecionado
        bot_id = query.data.replace("substituir_bot_", "")
        
        # Salva o bot selecionado no contexto
        context.user_data['bot_para_substituir'] = bot_id
        
        # Pede o novo token
        keyboard = [[InlineKeyboardButton("❌ CANCELAR", callback_data="registro_cancelar_substituir")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 <b>Novo Token</b>\n\n"
            "Agora envie o token do NOVO bot que substituirá o anterior.\n\n"
            "💡 <i>Crie um novo bot no @BotFather e envie o token aqui.</i>\n\n"
            "⚠️ <b>Atenção:</b> Todas as configurações serão copiadas automaticamente.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        return REGISTRO_AGUARDANDO_NOVO_TOKEN
    
async def registro_processar_novo_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verifica se é cancelamento
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == "registro_cancelar_substituir":
            await query.edit_message_text(
                "❌ <b>Substituição cancelada!</b>",
                parse_mode='HTML'
            )
            return ConversationHandler.END
    
    # Processa o novo token
    if update.message and update.message.text:
        new_token = update.message.text.strip()
        bot_id_antigo = context.user_data.get('bot_para_substituir')
        user_id = update.effective_user.id
        
        # Verifica se o token já existe
        if manager.bot_exists(new_token):
            await update.message.reply_text(
                '⚠️ <b>Este token já está cadastrado!</b>\n\n'
                'Use um token de um bot novo.',
                parse_mode='HTML'
            )
            return REGISTRO_AGUARDANDO_NOVO_TOKEN
        
        # Valida o novo token
        telegram_bot = manager.check_bot_token(new_token)
        if not telegram_bot or not telegram_bot.get('result'):
            await update.message.reply_text(
                '❌ <b>Token inválido!</b>\n\n'
                'Verifique se o token está correto.',
                parse_mode='HTML'
            )
            return REGISTRO_AGUARDANDO_NOVO_TOKEN
        
        # Pega informações do novo bot
        new_bot_info = telegram_bot['result']
        new_bot_id = str(new_bot_info.get('id'))
        new_bot_username = new_bot_info.get('username', 'sem_username')
        new_bot_name = new_bot_info.get('first_name', 'Sem nome')
        
        # Mensagem de processamento
        processing_msg = await update.message.reply_text(
            "⏳ <b>Substituindo bot...</b>\n\n"
            "Por favor, aguarde enquanto transferimos as configurações.",
            parse_mode='HTML'
        )
        
        try:
            # 1. Para o bot antigo se estiver rodando
            if bot_id_antigo in processes:
                try:
                    process = processes[bot_id_antigo]
                    if process:
                        process.terminate()
                        time.sleep(0.5)
                        if process.is_alive():
                            process.kill()
                        process.join(timeout=2)
                    processes.pop(bot_id_antigo)
                except:
                    pass
            
            # 2. Remove dos dados em memória
            if bot_id_antigo in bots_data:
                bots_data.pop(bot_id_antigo)
            
            # 3. Copia apenas configurações específicas
            bot_antigo = manager.get_bot_by_id(bot_id_antigo)
            if bot_antigo:
                # Prepara as configurações selecionadas
                
                # CONFIG - copia apenas textos do /inicio (sem mídia)
                config_data = json.loads(bot_antigo[3])
                config_limpa = {
                    'texto1': config_data.get('texto1', False),
                    'texto2': config_data.get('texto2', "Configure o bot usando /inicio\n\nUtilize /comandos para verificar os comandos existentes"),
                    'button': config_data.get('button', 'CLIQUE AQUI PARA VER OFERTAS')
                }
                
                # ADMIN - copia lista de admins
                admin_data = json.loads(bot_antigo[4])
                
                # PLANS - copia todos os planos
                plans_data = json.loads(bot_antigo[5])
                
                # GATEWAY - copia configuração de pagamento
                gateway_data = json.loads(bot_antigo[6])
                
                # GROUP - copia ID do grupo
                group_data = bot_antigo[9]
                
                # Cria o novo bot com configurações selecionadas
                manager.create_bot(
                    id=new_bot_id,
                    token=new_token,
                    owner=str(user_id),
                    config=config_limpa,      # config sem mídia
                    admin=admin_data,         # admins copiados
                    plans=plans_data,         # planos copiados
                    gateway=gateway_data,     # gateway copiado
                    users=[],                 # usuários vazio
                    upsell={},               # upsell vazio
                    group=group_data,        # grupo copiado
                    expiration={}            # expiração vazia
                )
                
                # 4. Deleta o bot antigo
                manager.delete_bot(bot_id_antigo)
                
                # 5. Inicia o novo bot
                start_bot(new_token, new_bot_id)
                
                # Prepara mensagem com instruções
                instrucoes = "\n\n⚠️ <b>AÇÕES NECESSÁRIAS:</b>\n\n"
                
                # Sempre mostra para adicionar o bot no grupo se houver grupo configurado
                if group_data:
                    instrucoes += f"1️⃣ Adicione o bot @{new_bot_username} como admin no grupo VIP\n"
                else:
                    instrucoes += "1️⃣ Configure o grupo VIP: /vip\n"
                
                # Sempre mostra todas as instruções
                instrucoes += (
                    "2️⃣ Configure a mídia inicial: /inicio\n"
                    "3️⃣ Reconfigure os seguintes comandos:\n"
                    "   • /expiracao - Mensagem de expiração\n"
                    "   • /upsell - Oferta de upsell\n"
                    "   • /downsell - Oferta de downsell\n"
                    "   • /recuperacao - Sistema de recuperação\n"
                    "   • /orderbump - Ofertas adicionais\n"
                    "   • /disparo - Disparos programados"
                )
                
                # Atualiza mensagem de sucesso
                await processing_msg.edit_text(
                    f"✅ <b>Bot substituído com sucesso!</b>\n\n"
                    f"<b>Bot antigo:</b> Removido\n"
                    f"<b>Novo bot:</b> {new_bot_name}\n"
                    f"<b>Username:</b> @{new_bot_username}\n\n"
                    f"✨ Configurações básicas transferidas!\n"
                    f"✨ O novo bot já está online!\n\n"
                    f"🔗 Link: t.me/{new_bot_username}"
                    f"{instrucoes}",
                    parse_mode='HTML'
                )
                
            else:
                await processing_msg.edit_text(
                    "❌ <b>Erro ao encontrar bot antigo!</b>",
                    parse_mode='HTML'
                )
                
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ <b>Erro ao substituir bot!</b>\n\n"
                f"Detalhes: {str(e)}",
                parse_mode='HTML'
            )
    
    return ConversationHandler.END

def main():
    """Função principal para rodar o bot de registro"""
    if not REGISTRO_TOKEN:
        print("Token de registro não configurado!")
        return
        
    registro_token = REGISTRO_TOKEN
    application = Application.builder().token(registro_token).build()
    
    # ConversationHandler para o fluxo de registro
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_func)],
        states={
            REGISTRO_MENU: [
                CallbackQueryHandler(registro_menu_callback),
            ],
            REGISTRO_AGUARDANDO_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token_register),
                CallbackQueryHandler(receive_token_register, pattern="^registro_cancelar_silencioso$"),
            ],
            REGISTRO_SELECIONAR_BOT: [
                CallbackQueryHandler(registro_selecionar_bot_callback),
            ],
            REGISTRO_AGUARDANDO_NOVO_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registro_processar_novo_token),
                CallbackQueryHandler(registro_processar_novo_token, pattern="^registro_cancelar_substituir$"),
            ],
        },
        fallbacks=[CommandHandler('start', start_func)],
    )
    
    application.add_handler(conv_handler)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print('Iniciando BOT de Registro')
    application.run_polling()

def start_register():
    register = Process(target=main)
    register.start()

@app.route('/dashboard-data', methods=['GET'])
def get_dashboard_data():
    if session.get("auth", False):
        dashboard_data['botsActive'] = len(processes)
        dashboard_data['usersCount'] = '?'
        dashboard_data['salesCount'] = len(manager.get_all_payments_by_status('finished'))
        return jsonify(dashboard_data)
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/bots', methods=['GET'])
def bots():
    if session.get("auth", False):
        bot_list = manager.get_all_bots()
        bots = []

        for bot in bot_list:
            bot_details = manager.check_bot_token(bot[1])
            bot_structure = {
                'id': bot[0],
                'token': bot[1],
                'url': "Token Inválido",
                'owner': bot[2],
                'data': json.loads(bot[3])
            }
            if bot_details:
                bot_structure['url'] = f'https://t.me/{bot_details['result'].get('username', "INDEFINIDO")}'
            
            bots_data[str(bot[0])] = bot_structure
            bots.append(bot_structure)
        return jsonify(bots)
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/terminal', methods=['POST'])
def terminal():
    if session.get("auth", False):
        data = request.get_json()
        command = data.get('command', '').strip()
        if not command:
            return jsonify({"response": "Comando vazio. Digite algo para enviar."}), 400
        
        response = f"Comando '{command}' recebido com sucesso. Processado às {time.strftime('%H:%M:%S')}."
        return jsonify({"response": response})
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check para o Railway"""
    return jsonify({
        "status": "healthy",
        "bots_active": len(processes),
        "timestamp": datetime.datetime.now().isoformat()
    })
    
@app.route('/admin/bots', methods=['GET'])
def admin_bots():
    if session.get("auth", False):
        return send_file('./templates/admin_bots.html')
    return redirect(url_for('login'))

@app.route('/api/bots/active', methods=['GET'])
def get_active_bots():
    if session.get("auth", False):
        # Retorna bots ativos com status dos processos
        active_bots = []
        all_bots = manager.get_all_bots()
        
        for bot in all_bots:
            bot_id = str(bot[0])
            bot_token = bot[1]
            
            bot_info = {
                'id': bot_id,
                'token': bot_token,
                'owner': bot[2],
                'status': 'inactive',  # Default
                'username': 'Carregando...',
                'name': 'Sem nome'  # Default
            }
            
            # Verifica se o processo está ativo
            if bot_id in processes:
                if processes[bot_id] and processes[bot_id].is_alive():
                    bot_info['status'] = 'active'
                else:
                    bot_info['status'] = 'inactive'
            
            # Tenta pegar username e nome do bot
            try:
                bot_details = manager.check_bot_token(bot_token)
                if bot_details and bot_details.get('result'):
                    bot_info['username'] = bot_details['result'].get('username', 'INDEFINIDO')
                    bot_info['name'] = bot_details['result'].get('first_name', 'Sem nome')
            except:
                bot_info['username'] = 'Token Inválido'
                bot_info['name'] = 'Erro'
            
            active_bots.append(bot_info)
        
        return jsonify(active_bots)
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/api/bot/ban/<bot_id>', methods=['POST'])
def ban_bot(bot_id):
    if session.get("auth", False):
        bot = manager.get_bot_by_id(bot_id)
        if bot:
            bot_token = bot[1]
            owner_id = bot[2]
            
            # 1. PRIMEIRO envia a notificação através do PRÓPRIO BOT do cliente
            try:
                # Pega detalhes do bot
                bot_details = manager.check_bot_token(bot_token)
                bot_username = bot_details['result'].get('username', 'Bot') if bot_details else 'Bot'
                
                message = (
                    "🚫 <b>ATENÇÃO: ESTE BOT FOI BANIDO</b> 🚫\n\n"
                    f"<b>Bot:</b> @{bot_username}\n"
                    f"<b>ID:</b> {bot_id}\n\n"
                    "❌ Este bot será desligado em instantes.\n"
                    "❌ Todos os dados serão apagados.\n"
                    "❌ Esta ação é permanente e irreversível.\n\n"
                    "⚠️ <b>O bot parará de funcionar agora.</b>\n\n"
                    "Para mais informações, entre em contato com o suporte."
                )
                
                # Envia usando o TOKEN DO PRÓPRIO BOT
                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": owner_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )
                print(f"Notificação enviada através do bot {bot_username}: {response.status_code}")
                
                # Aguarda 2 segundos para garantir que a mensagem foi enviada
                time.sleep(2)
                
            except Exception as e:
                print(f"Erro ao enviar notificação através do bot do cliente: {e}")
            
            # 2. Para TODOS os processos que usam este token
            # IMPORTANTE: Procura por token, não só por ID
            for pid, process in list(processes.items()):
                if pid == str(bot_id) or (pid in bots_data and bots_data[pid].get('token') == bot_token):
                    try:
                        if process:
                            # Envia SIGTERM
                            process.terminate()
                            time.sleep(0.5)
                            
                            # Se ainda estiver vivo, SIGKILL
                            if process.is_alive():
                                process.kill()
                                time.sleep(0.5)
                            
                            # Aguarda o processo realmente terminar
                            process.join(timeout=2)
                        
                        # Remove do dicionário de processos
                        processes.pop(pid, None)
                        print(f"Processo {pid} parado com sucesso")
                    except Exception as e:
                        print(f"Erro ao parar processo {pid}: {e}")
                    
                    # Remove dos dados em memória
                    if pid in bots_data:
                        bots_data.pop(pid)
            
            # 3. Remove o token da lista global
            if bot_token in tokens:
                tokens.remove(bot_token)
            
            # 4. Deleta do banco de dados
            success = manager.delete_bot(bot_id)
            
            if success:
                return jsonify({
                    "success": True, 
                    "message": f"Bot {bot_id} banido e removido com sucesso!"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Erro ao remover bot do banco de dados"
                }), 500
        
        return jsonify({"error": "Bot não encontrado"}), 404
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/check-inactive', methods=['GET'])
def check_inactive():
    """Endpoint interno para verificar bots inativos"""
    check_and_remove_inactive_bots()
    return jsonify({"status": "checked"})

if __name__ == '__main__':
    print(f"Iniciando aplicação na porta {port}")
    print(f"URL configurada: {IP_DA_VPS}")
    
    manager.inicialize_database()
    manager.create_recovery_tracking_table()
    initialize_all_registered_bots()
    start_register()
    
    # Inicia thread de verificação de inatividade
    import threading
    inactivity_thread = threading.Thread(target=inactivity_checker_thread, daemon=True)
    inactivity_thread.start()
    
    app.run(debug=False, host='0.0.0.0', port=port)
