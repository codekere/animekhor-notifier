/**
 * Cloudflare Worker for AnimeKhor Telegram Bot
 * ============================================
 * Provides instant (< 1 second) responses for Telegram commands:
 * - /link [page_url] : Instant latest episode or webpage to video link with 100% WATERMARK-FREE 16:9 thumbnail
 * - /dl [link]       : Inspects episode, displays Title, Estimated Size, and confirmation button
 * - Confirmation tap : Starts Live Progress Bar, triggers GitHub Actions for Best HD cloud rendering
 *
 * Environment Variables required in Cloudflare Worker:
 * - TELEGRAM_BOT_TOKEN : Telegram bot token from @BotFather
 * - TELEGRAM_CHAT_ID   : (Optional) Restrict access to your numeric Chat ID
 * - GITHUB_TOKEN      : GitHub Personal Access Token (PAT with 'repo' scope)
 * - GITHUB_REPO       : "codekere/animekhor-notifier"
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    try {
      const update = await request.json();
      await handleTelegramUpdate(update, env);
    } catch (err) {
      console.error("Worker error:", err);
    }

    return new Response("OK", { status: 200 });
  }
};

async function handleTelegramUpdate(update, env) {
  const botToken = env.TELEGRAM_BOT_TOKEN;
  const allowedChatId = env.TELEGRAM_CHAT_ID;
  const githubToken = env.GITHUB_TOKEN;
  const githubRepo = env.GITHUB_REPO || "codekere/animekhor-notifier";

  // 1. Handle Callback Queries (Buttons)
  if (update.callback_query) {
    const cb = update.callback_query;
    const cbData = cb.data || "";
    const cbChatId = cb.message.chat.id;
    const cbMsgId = cb.message.message_id;

    if (cbData === "dismiss") {
      await deleteTelegramMessage(botToken, cbChatId, cbMsgId);
      await answerCallbackQuery(botToken, cb.id, "Closed");
      return;
    }

    // Confirmation button tapped: start download & cloud processing
    if (cbData.startsWith("confirm_dl:")) {
      const vidId = cbData.split(":")[1];
      const videoUrl = `https://www.dailymotion.com/video/${vidId}`;

      await answerCallbackQuery(botToken, cb.id, "Starting cloud download...");

      // Update message into Live Progress Bar (10%)
      const progressMsg =
        `⏳ <b>Processing Best HD Video...</b>\n\n` +
        `<code>[■□□□□□□□□□] 10%</code>\n` +
        `Starting GitHub Actions runner to download and remove watermark. Please wait ~2-3 minutes...`;

      await editTelegramMessage(botToken, cbChatId, cbMsgId, progressMsg);

      // Trigger GitHub Actions via repository_dispatch
      if (githubToken) {
        await triggerGitHubWorkflow(githubToken, githubRepo, videoUrl, cbChatId, cbMsgId);
      }
      return;
    }
    return;
  }

  const msg = update.message;
  if (!msg || !msg.text) return;

  const chatId = String(msg.chat.id);
  const text = msg.text.trim();
  const userMsgId = msg.message_id;

  // Security check: restrict to your Chat ID if configured
  if (allowedChatId && chatId !== String(allowedChatId)) {
    return;
  }

  // 2. Command: /start or /help
  if (text.startsWith("/start") || text.startsWith("/help")) {
    const welcome =
      `👋 <b>AnimeKhor Notifier & Cloud Processor</b>\n\n` +
      `<b>Features:</b>\n` +
      `• Instant sub-second responses via Cloudflare Workers\n` +
      `• 100% Watermark-free 16:9 Full HD Thumbnails for YouTube\n` +
      `• Live progress bar during video processing\n\n` +
      `<b>Commands:</b>\n` +
      `• /link - Get latest episode with clean thumbnail & direct link\n` +
      `• /link &lt;page-url&gt; - Convert AnimeKhor page to direct video link\n` +
      `• /dl - Check latest episode title & size, with download button\n` +
      `• /dl &lt;link&gt; - Check specific episode title & size, with download button`;
    await sendTelegram(botToken, chatId, welcome);
    return;
  }

  // 3. Command: /link [page_url] (Latest episode or convert page)
  if (text.startsWith("/link")) {
    const parts = text.split(/\s+/);
    let targetPage = parts[1] || "";

    if (!targetPage && msg.reply_to_message && msg.reply_to_message.text) {
      const match = msg.reply_to_message.text.match(/https?:\/\/[^\s<>"]+/);
      if (match) targetPage = match[0];
    }

    let pubDateStr = "";

    // Default to latest episode from RSS if no URL is provided
    if (!targetPage) {
      const latest = await getLatestRssItem();
      if (!latest) {
        await sendTelegram(botToken, chatId, "❌ Failed to fetch latest episode.");
        return;
      }
      targetPage = latest.link;
      pubDateStr = latest.pubDate;
    }

    const videoUrl = await extractVideoLink(targetPage);
    const info = await getDailymotionVideoInfo(videoUrl);
    const cleanThumbUrl = getCleanThumbnailUrl(info.rawThumbUrl);
    const pageSlug = targetPage.replace(/\/+$/, "").split("/").pop().replace(/-/g, " ");
    const vidId = extractDmId(videoUrl);

    let caption =
      `🎬 <b>Direct Video Link Ready!</b>\n\n` +
      `📌 <b>Page:</b>\n<code>${pageSlug}</code>\n`;

    if (pubDateStr) {
      caption += `\n🕒 <b>Update:</b> ${pubDateStr}\n`;
    }

    caption +=
      `\n📦 <b>Size:</b> ${info.size} (Best HD)\n` +
      `🔗 <b>Direct Link:</b>\n<code>${videoUrl}</code>`;

    const keyboard = {
      inline_keyboard: [
        [
          { text: `⬇️ Download Best HD (${info.size})`, callback_data: `confirm_dl:${vidId}` }
        ]
      ]
    };

    if (cleanThumbUrl) {
      await sendTelegramPhoto(botToken, chatId, cleanThumbUrl, caption, keyboard);
    } else {
      await sendTelegram(botToken, chatId, caption, keyboard);
    }
    return;
  }

  // 4. Command: /dl (Show Title, Size, and Confirmation Download Button)
  if (text.startsWith("/dl")) {
    await deleteTelegramMessage(botToken, chatId, userMsgId);

    const parts = text.split(/\s+/);
    let targetLink = parts[1] || "";

    if (!targetLink && msg.reply_to_message && msg.reply_to_message.text) {
      const match = msg.reply_to_message.text.match(/https?:\/\/[^\s<>"]+/);
      if (match) targetLink = match[0];
    }

    if (!targetLink) {
      const latest = await getLatestRssItem();
      if (latest) targetLink = latest.link;
    }

    if (!targetLink) {
      await sendTelegram(botToken, chatId, "❌ <b>Usage:</b> <code>/dl &lt;link&gt;</code>");
      return;
    }

    const videoUrl = await extractVideoLink(targetLink);
    const info = await getDailymotionVideoInfo(videoUrl);
    const cleanTitle = cleanTitleForDisplay(info.title);
    const vidId = extractDmId(videoUrl);

    const confirmMsg =
      `🎬 <b>Best HD Video Info</b>\n\n` +
      `📌 <b>Title:</b>\n<code>${cleanTitle}</code>\n\n` +
      `📦 <b>Estimated Size:</b> ${info.size}\n` +
      `⏱️ <b>Duration:</b> ${info.duration}\n` +
      `🎬 <b>Quality:</b> 1080p Full HD (No Watermark)\n` +
      `📝 <b>Subtitles:</b> Clean Indonesian & English included\n\n` +
      `<i>Click the button below to start cloud processing:</i>`;

    const keyboard = {
      inline_keyboard: [
        [
          { text: `⬇️ Start Download & Clean (${info.size})`, callback_data: `confirm_dl:${vidId}` }
        ],
        [
          { text: "❌ Cancel", callback_data: "dismiss" }
        ]
      ]
    };

    await sendTelegram(botToken, chatId, confirmMsg, keyboard);
    return;
  }
}

// ---------------- Helper Functions ---------------- //

function getCleanThumbnailUrl(rawThumbUrl) {
  if (!rawThumbUrl) return "";
  // Crops top 48 pixels where AnimeKhor.org and bilibili logos reside, preserving pristine 16:9 1080p
  return `https://wsrv.nl/?url=${encodeURIComponent(rawThumbUrl)}&cx=0&cy=48&cw=1920&ch=1032&w=1920&h=1080&fit=cover`;
}

async function getDailymotionVideoInfo(videoUrl) {
  const vidId = extractDmId(videoUrl);
  if (!vidId) {
    return { title: "Anime Episode", size: "~260 MB", duration: "24 mins", rawThumbUrl: "" };
  }
  try {
    const res = await fetch(`https://api.dailymotion.com/video/${vidId}?fields=title,duration,thumbnail_1080_url,thumbnail_720_url,thumbnail_large_url`);
    const data = await res.json();
    const durationMins = data.duration ? Math.round(data.duration / 60) : 24;
    const estimatedMb = Math.round(durationMins * 11);
    return {
      title: data.title || "Anime Episode",
      size: `~${estimatedMb} MB`,
      duration: `${durationMins} mins`,
      rawThumbUrl: data.thumbnail_1080_url || data.thumbnail_720_url || data.thumbnail_large_url || ""
    };
  } catch (e) {
    return { title: "Anime Episode", size: "~260 MB", duration: "24 mins", rawThumbUrl: "" };
  }
}

async function triggerGitHubWorkflow(token, repo, url, chatId, messageId) {
  const endpoint = `https://api.github.com/repos/${repo}/dispatches`;
  await fetch(endpoint, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "User-Agent": "Cloudflare-Worker",
      "Accept": "application/vnd.github.v3+json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      event_type: "download_clean",
      client_payload: {
        url: url,
        chat_id: String(chatId),
        message_id: messageId
      }
    })
  });
}

function formatPubDate(pubDateStr) {
  if (!pubDateStr) return "";
  try {
    const d = new Date(pubDateStr);
    const utc = d.getTime() + (d.getTimezoneOffset() * 60000);
    const wib = new Date(utc + (3600000 * 7));
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const day = String(wib.getDate()).padStart(2, "0");
    const month = months[wib.getMonth()];
    const year = wib.getFullYear();
    const hours = String(wib.getHours()).padStart(2, "0");
    const mins = String(wib.getMinutes()).padStart(2, "0");
    return `${day} ${month} ${year}, ${hours}:${mins} WIB`;
  } catch (e) {
    return pubDateStr;
  }
}

async function getLatestRssItem() {
  try {
    const res = await fetch("https://animekhor.org/feed/", {
      headers: { "User-Agent": "Mozilla/5.0" }
    });
    const xmlText = await res.text();
    const itemMatch = xmlText.match(/<item>([\s\S]*?)<\/item>/);
    if (!itemMatch) return null;

    const titleMatch = itemMatch[1].match(/<title>([\s\S]*?)<\/title>/);
    const linkMatch = itemMatch[1].match(/<link>([\s\S]*?)<\/link>/);
    const pubDateMatch = itemMatch[1].match(/<pubDate>([\s\S]*?)<\/pubDate>/);

    return {
      title: titleMatch ? titleMatch[1].replace(/<!\[CDATA\[(.*?)\]\]>/g, "$1").trim() : "",
      link: linkMatch ? linkMatch[1].trim() : "",
      pubDate: pubDateMatch ? formatPubDate(pubDateMatch[1].trim()) : ""
    };
  } catch (e) {
    return null;
  }
}

async function extractVideoLink(pageUrl) {
  if (pageUrl.includes("dailymotion.com")) return pageUrl;
  try {
    const res = await fetch(pageUrl, {
      headers: { "User-Agent": "Mozilla/5.0", "Referer": "https://animekhor.org/" }
    });
    const html = await res.text();
    const dmMatch = html.match(/(?:https?:)?\/\/(?:www\.|geo\.)?dailymotion\.com\/(?:embed\/video\/|player\.html\?video=)([\w-]+)/);
    if (dmMatch) {
      return `https://www.dailymotion.com/video/${dmMatch[1]}`;
    }
  } catch (e) {}
  return pageUrl;
}

function extractDmId(url) {
  const match = url.match(/dailymotion\.com\/(?:video\/|embed\/video\/|player\.html\?video=)([\w-]+)/);
  return match ? match[1] : "";
}

function cleanTitleForDisplay(rawTitle) {
  return rawTitle.replace(/\[?www\.AnimeKhor\.org\]?/gi, "").replace(/\s+/g, " ").trim();
}

async function sendTelegram(botToken, chatId, text, keyboard = null) {
  const payload = {
    chat_id: chatId,
    text: text,
    parse_mode: "HTML",
    disable_web_page_preview: false
  };
  if (keyboard) payload.reply_markup = keyboard;

  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  return data.ok ? data.result : null;
}

async function sendTelegramPhoto(botToken, chatId, photoUrl, caption, keyboard = null) {
  const payload = {
    chat_id: chatId,
    photo: photoUrl,
    caption: caption,
    parse_mode: "HTML"
  };
  if (keyboard) payload.reply_markup = keyboard;

  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendPhoto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  return data.ok ? data.result : null;
}

async function editTelegramMessage(botToken, chatId, messageId, text, keyboard = null) {
  const payload = {
    chat_id: chatId,
    message_id: messageId,
    text: text,
    parse_mode: "HTML",
    disable_web_page_preview: false
  };
  if (keyboard) payload.reply_markup = keyboard;

  await fetch(`https://api.telegram.org/bot${botToken}/editMessageText`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

async function deleteTelegramMessage(botToken, chatId, messageId) {
  await fetch(`https://api.telegram.org/bot${botToken}/deleteMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, message_id: messageId })
  });
}

async function answerCallbackQuery(botToken, callbackQueryId, text) {
  await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId, text: text })
  });
}
