require('dotenv').config();

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');
const path = require('path');

// ===================================================
// ENV
// ===================================================

// ===================================================
// CONFIGURAÇÕES
// ===================================================

// Seu número pessoal, somente dígitos com DDI. Ex: 5575999999999
const SEU_NUMERO = process.env.SE_NUMBER || process.env.SEU_NUMERO || '';

// Backend Python centraliza NLP, estados pendentes e persistência.
const BOT_API_URL = process.env.BOT_API_URL || 'http://localhost:8000';
const MESSAGE_API_URL = `${BOT_API_URL.replace(/\/$/, '')}/message`;
const AUDIO_API_URL = `${BOT_API_URL.replace(/\/$/, '')}/audio`;

// Pasta temporária para áudios
const AUDIO_DIR = path.join(__dirname, 'audios');
if (!fs.existsSync(AUDIO_DIR)) fs.mkdirSync(AUDIO_DIR);

// ===================================================
// CLIENTE WHATSAPP
// ===================================================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: process.env.WA_HEADLESS === 'true',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// ===================================================
// BACKEND PYTHON
// ===================================================
async function enviarParaBackend(userId, text) {
    const response = await axios.post(
        MESSAGE_API_URL,
        { user_id: userId, text },
        { timeout: 30000 }
    );

    return response.data?.reply || '✅ Processado.';
}

// ===================================================
// EVENTOS BÁSICOS
// ===================================================
client.on('qr', (qr) => {
    console.log('\n📱 Escaneie o QR Code com o CELULAR DO BOT');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('\n✅ Bot conectado com sucesso');
    console.log(`🤖 Aguardando mensagens do número: ${SEU_NUMERO || '(não configurado)'}`);
    console.log(`🔗 Backend: ${BOT_API_URL}`);
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
        if (msg.fromMe) return;
        if (msg.from.endsWith('@g.us')) return;
        if (msg.from === 'status@broadcast') return;

        if (!SEU_NUMERO) {
            console.error('❌ Configure SE_NUMBER no .env antes de usar o bot.');
            return;
        }

        const fromNumber = normalize(msg.from);
        if (fromNumber !== SEU_NUMERO) return;

        // ===============================
        // 🎤 ÁUDIO
        // ===============================
        if (msg.hasMedia && msg.type === 'ptt') {
            const media = await msg.downloadMedia();
            const buffer = Buffer.from(media.data, 'base64');

            const fileName = `audio_${Date.now()}.ogg`;
            const filePath = path.join(AUDIO_DIR, fileName);

            try {
                fs.writeFileSync(filePath, buffer);

                const form = new FormData();
                form.append('audio', fs.createReadStream(filePath));

                const response = await axios.post(AUDIO_API_URL, form, {
                    headers: form.getHeaders(),
                    timeout: 60000,
                    maxBodyLength: 25 * 1024 * 1024
                });

                const transcribedText = response.data.text;

                if (!transcribedText) {
                    await msg.reply('❌ Não consegui transcrever o áudio.');
                    return;
                }

                const reply = await enviarParaBackend(fromNumber, transcribedText);
                await msg.reply(reply);
                return;
            } finally {
                fs.unlink(filePath, () => {});
            }
        }

        // ===============================
        // 💬 TEXTO NORMAL → PLANILHA
        // ===============================
        if (msg.body && msg.body.trim()) {
            console.log('💬 Texto recebido');

            const reply = await enviarParaBackend(fromNumber, msg.body.trim());
            await msg.reply(reply);
        }

    } catch (err) {
        console.error(
            '❌ Erro geral no processamento:',
            err.response?.status || err.message
        );

        try {
            await msg.reply(
                `❌ *Erro ao atualizar a planilha*

Não consegui salvar esse gasto.
Tente novamente.`
            );
        } catch (_) { }
    }
});

// ===================================================
// START
// ===================================================
client.initialize();
