const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');
const path = require('path');

// ===================================================
// CONFIGURAÇÕES
// ===================================================

// SEU NÚMERO (quem ENVIA a mensagem)
const SEU_NUMERO = '557592238338';

// Backend Python
const API_URL = 'http://127.0.0.1:8002/message';
const AUDIO_API_URL = 'http://127.0.0.1:8002/audio';

// Pasta temporária para áudios
const AUDIO_DIR = path.join(__dirname, 'audios');
if (!fs.existsSync(AUDIO_DIR)) fs.mkdirSync(AUDIO_DIR);

// ===================================================
// CLIENTE WHATSAPP
// ===================================================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: false,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// ===================================================
// EVENTOS BÁSICOS
// ===================================================
client.on('qr', (qr) => {
    console.log('\n📱 Escaneie o QR Code com o CELULAR DO BOT');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('\n✅ Bot conectado com sucesso');
    console.log(`🤖 Aguardando mensagens do número: ${SEU_NUMERO}`);
});

// ===================================================
// UTIL
// ===================================================
function normalize(id) {
    return id.replace(/\D/g, '');
}

// ===================================================
// PROCESSAMENTO
// ===================================================
client.on('message', async (msg) => {
    try {
        // Ignorar mensagens do próprio bot
        if (msg.fromMe) return;

        // Ignorar grupos e status
        if (msg.from.endsWith('@g.us')) return;
        if (msg.from === 'status@broadcast') return;

        // Validar número
        const fromNumber = normalize(msg.from);
        if (fromNumber !== SEU_NUMERO) return;

        // ===============================
        // 🎤 ÁUDIO
        // ===============================
        if (msg.hasMedia && msg.type === 'ptt') {
            console.log('🎤 Áudio recebido, baixando...');

            const media = await msg.downloadMedia();
            const buffer = Buffer.from(media.data, 'base64');

            const fileName = `audio_${Date.now()}.ogg`;
            const filePath = path.join(AUDIO_DIR, fileName);

            fs.writeFileSync(filePath, buffer);

            console.log('🔄 Enviando áudio para transcrição...');

            const form = new FormData();
            form.append('audio', fs.createReadStream(filePath));

            const response = await axios.post(AUDIO_API_URL, form, {
                headers: form.getHeaders()
            });

            const transcribedText = response.data.text;

            console.log('📝 Transcrição:', transcribedText);

            // Enviar texto transcrito para o backend normal
            const finalResponse = await axios.post(API_URL, {
                user_id: fromNumber,
                text: transcribedText
            });

            if (finalResponse.data?.reply) {
                await msg.reply(`🎤 "${transcribedText}"\n\n${finalResponse.data.reply}`);
            }

            return;
        }

        // ===============================
        // 💬 TEXTO NORMAL
        // ===============================
        if (msg.body && msg.body.trim()) {
            console.log('💬 Texto recebido:', msg.body);

            const response = await axios.post(API_URL, {
                user_id: fromNumber,
                text: msg.body
            });

            if (response.data?.reply) {
                await msg.reply(response.data.reply);
            }
        }

    } catch (err) {
        console.error('❌ Erro:', err.message);
        await msg.reply('⚠️ Erro ao processar a mensagem.');
    }
});

// ===================================================
// START
// ===================================================
client.initialize();